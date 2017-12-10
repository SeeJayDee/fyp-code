# === classes.py ===
# * Function: a container for custom classes pertaining to olimex-emg-read.
# *
# * This is part of Christian D'Abrera's engineering final
# * year project titled "EMG Bio-feedback for rehabilitation".
# *
# * Christian D'Abrera
# * Curtin University 2017
# * christian.dabrera@student.curtin.edu.au
# * chrisdabrera@gmail.com

"""A library for the various object classes used in olimex-emg-read.py.

Yep.
"""

from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import numpy as np
from scipy import signal
from collections import deque
from threading import Thread
import threading
import serial
import datetime
import time
import keylib as kl
# from functools import partial

app = QtGui.QApplication([])  # apparently this is necessary

# borrowed from HUMM Tech; never used
# def runningMeanFast(x, N):
#     return np.convolve(x, np.ones((N,))/N)[(N-1):]


# unimplemented calibration feature
class cal_pattern(object):
    """An object to contain parameters for each calibration pattern.

    Contains lists in a dict, having keys:
        'C': list of channels the user will be asked to activate on CUE
        'S': list of channels the user will be asked to keep tensed STATIC
    Other parameters are: number of repeats, on time, off time.
    """

    def __init__(self, repeats, cue_chans, stat_chans, times):
        """Constructor."""
        self.repeats = repeats
        self.cued = cue_chans
        self.static = stat_chans
        self.t_on = times[0]
        self.t_off = times[1]


class DisplayWindow(object):
    """A generic wrapper for our QtGui window.

    Will contain all the functions for the plotting and data output.
    """

    def __init__(self, cfg):
        """Constructor."""
        self.cfg = cfg  # store config info internally

        # state variables
        self.docalibration = False
        self.sendkeys = False
        self.chanstates = {}
        for name in cfg['names']:
            self.chanstates[name] = False

        # keyboard event things
        cfg['keys'] = kl.Base
        self.combo_map = []
        self.selected_keys = []

        # window & dialog setup
        self.mainwin = QtGui.QMainWindow()
        self.calibrator = calDialog(cfg, self)  # unimplemented
        self.keyselect = keysDialog(cfg, self)

        # set window properties, central widget, layouts, control bar
        self.mainwin.setWindowTitle(cfg['title'])
        self.mainwin.resize(cfg['width'], cfg['height'])
        self.central_widget = QtGui.QWidget()
        self.mainwin.setCentralWidget(self.central_widget)
        self.mainbar = QtGui.QVBoxLayout()
        self.top_layout = QtGui.QHBoxLayout()
        self.side_layouts = {'left': QtGui.QVBoxLayout(),
                             'right': QtGui.QVBoxLayout()}
        self.top_layout.addLayout(self.side_layouts['left'])
        self.top_layout.addLayout(self.side_layouts['right'])
        self.top_layout.addLayout(self.mainbar)
        self.central_widget.setLayout(self.top_layout)

        # mainbar widgets setup
        self.mb_widgets = {}
        self.mb_widgets['streamctl'] = QtGui.QPushButton('Start streaming')
        self.mb_widgets['streamctl'].clicked.connect(self.btn_streamctl_click)

        self.mb_widgets['dorecord'] = QtGui.QCheckBox('Record output')
        self.mb_widgets['dorecord'].stateChanged.connect(self.chbox_dorecord_changed)

        self.mb_widgets['loadcfg'] = QtGui.QPushButton('Load config')
        # self.mb_widgets['loadcfg'].clicked.connect(self.btn_loadcfg_click)

        self.mb_widgets['cal'] = QtGui.QPushButton('Calibrate')
        # self.mb_widgets['cal'].clicked.connect(self.btn_cal_click)

        self.mb_widgets['sendkeys'] = QtGui.QCheckBox('Send keyboard events')
        self.mb_widgets['sendkeys'].stateChanged.connect(self.chbox_sendkeys_changed)

        self.mb_widgets['keycfg'] = QtGui.QPushButton('Configure keys')
        self.mb_widgets['keycfg'].clicked.connect(self.btn_keycfg_click)

        # mainbar layout setup
        self.mainbar.addWidget(self.mb_widgets['streamctl'])
        self.mainbar.addWidget(self.mb_widgets['dorecord'])
        self.mainbar.addSpacing(1)
        self.mainbar.addWidget(self.mb_widgets['loadcfg'])
        self.mainbar.addWidget(self.mb_widgets['cal'])
        self.mainbar.addSpacing(1)
        self.mainbar.addWidget(self.mb_widgets['keycfg'])
        self.mainbar.addWidget(self.mb_widgets['sendkeys'])
        self.mainbar.addStretch(1)

        # timers & data structures
        self.plot_timer = QtCore.QTimer()
        self.plot_timer.timeout.connect(self.update_plots)
        plot_names = cfg['plot_names']
        self.plot_names = plot_names
        plot_colours = {2: (255, 111, 055),
                        3: (055, 111, 255),
                        4: (255, 99, 111),
                        5: (111, 99, 255)}
        # pre-initializing lots of dicts
        self.plotwidgets = {}
        self.plotcontrols = {}
        self.plots = {}
        self.datalen = 4 * cfg['sampfreq']
        self.data = {}
        self.ffts = {}
        self.fftlen = cfg['sampfreq'] / 4
        self.fftcount = self.fftlen / 8
        self.detect_time = {}
        self.cal_thread = None  # unimplemented

        for plt in plot_names:
            # set up the plot area & plot controls & threshold controls
            self.plotwidgets[plt] = pg.PlotWidget(name=plt)
            bar = {}
            bar['tlabel'] = QtGui.QLabel('Threshold (p-p): ')
            bar['tctlbox'] = QtGui.QSpinBox()
            bar['tctlbox'].setRange(0, 1023)
            bar['tctlbox'].setSingleStep(1)
            bar['tctlbox'].setSuffix(' counts')
            bar['tctlbox'].setValue(0)
            bar['detected'] = QtGui.QLabel('DETECT', )
            bar['layout'] = QtGui.QHBoxLayout()
            bar['layout'].addWidget(bar['tlabel'])
            bar['layout'].addWidget(bar['tctlbox'])
            bar['layout'].addWidget(bar['detected'])
            self.detect_time[plt] = 0.0
            bar['hbox'] = QtGui.QGroupBox('Channel {} (\'{}\' on ADC{}) controls'.format(cfg['names'][plt], plt, (cfg['indices'][plt] - 2)))
            bar['hbox'].setLayout(bar['layout'])
            self.plotcontrols[plt] = bar
            self.plots[plt] = self.plotwidgets[plt].plot()
            self.plots[plt].setPen(plot_colours[cfg['indices'][plt]])
            # if plt.startswith('L'):
            if plt.startswith('th'):
                self.side_layouts['left'].addWidget(self.plotwidgets[plt])
                self.side_layouts['left'].addWidget(bar['hbox'])
            # elif plt.startswith('R'):
            elif plt.startswith('fi'):
                self.side_layouts['right'].addWidget(self.plotwidgets[plt])
                self.side_layouts['right'].addWidget(bar['hbox'])

            self.data[plt] = deque([0.0]*self.datalen, self.datalen)
            self.ffts[plt] = np.zeros(self.fftlen / 2)  # len(rfft) = fftlen/2

            self.plotwidgets[plt].setRange(yRange=(0., 1024.))

        # testing plots by adding sine wave data (?)
        for i in xrange(0, self.datalen):
            for plt in plot_names:
                self.data[plt].appendleft(np.sin(i/10.))
                if i == self.datalen - 1:
                    self.plots[plt].setData(self.data[plt])

        self.plot_timer.start(cfg['plot_timer_ms'])
        self.mainwin.show()

    def update_plots(self):
        """Update all plots and perform threshold detection.

        Call sendkeys if necesssary.
        """
        title_string = self.cfg['title']
        for plt in self.plot_names:
            threshold = self.plotcontrols[plt]['tctlbox'].value()
            # self.plots[plt].setData(self.ffts[plt])
            self.plots[plt].setData(self.data[plt])
            title_string += '\
                | {0} p-p : {1:.0f}\
                '.format(plt, np.amax(self.data[plt]) - np.amin(self.data[plt]))
            # if  time.time() > self.detect_time[plt]:
            fresh = np.fromiter(self.data[plt], np.float, 64)
            if (np.amax(fresh) - np.amin(fresh)) > threshold:
                # self.detect_time[plt] = time.time() + 0.25
                self.plotcontrols[plt]['detected'].setText('DETECT')
                self.chanstates[plt] = True
                # print np.amax(self.data[plt])
            else:
                self.plotcontrols[plt]['detected'].setText('none')
                self.chanstates[plt] = False
        self.mainwin.setWindowTitle(title_string)
        if self.sendkeys:
            self.send_keys()
        app.processEvents()  # trigger graphics update

    def clear_plots(self):
        """Convert all plots to flatline.

        There is probably a better way to do this.
        """
        for plt in self.plot_names:
            q = self.data[plt]
            flatline = q[0]
            for _ in xrange(0, self.datalen):
                q.appendleft(flatline)
        return

    # def threshold_changed(self, chname):
    #     print chname
    #     self.thresholds[chname] = self.plotcontrols[chname]['tctlbox'].value()

    def send_keys(self):
        """Check channel states and send keyboard events."""
        for i in range(0, len(self.selected_keys)):
            # iterate over the list of keys we're sending
            Key = self.selected_keys[i]
            if Key:  # check if key is not None
                press_cond = self.combo_map[i]
                do_press = True
                for name in self.cfg['names']:
                    # if so check each channel state against entry in combo_map
                    # call keyDown if match, keyUp if no match
                    if press_cond[name] == QtCore.Qt.CheckState.Checked:
                        do_press = do_press & self.chanstates[name]
                    elif press_cond[name] == QtCore.Qt.CheckState.Unchecked:
                        do_press = do_press & (not self.chanstates[name])
                if do_press:
                    kl.KeyDown(Key, True)
                else:
                    kl.KeyUp(Key, True)
        return

    def btn_streamctl_click(self):
        """Start or stop parsing serial data."""
        caller = 'streamctl'  # tried, but can't pass args to Qt event funcs
        if self.cfg['handler'].do_polling:
            self.cfg['handler'].do_polling = False
            self.mb_widgets[caller].setText('Start streaming')
            self.clear_plots()
            self.enable_widgets(self.mb_widgets.values())
        else:
            self.cfg['handler'].do_polling = True
            self.mb_widgets[caller].setText('Stop streaming')
            disable_list = self.mb_widgets.values()
            disable_list.remove(self.mb_widgets['sendkeys'])
            disable_list.remove(self.mb_widgets[caller])
            self.disable_widgets(disable_list)

    def chbox_dorecord_changed(self):
        """Toggle recording to file."""
        caller = 'dorecord'
        self.cfg['handler'].nowrite = not self.mb_widgets[caller].isChecked()
        # self.cfg['handler'].nowrite = True
        # print self.cfg['handler'].nowrite
        print 'Recording: {}'.format(self.mb_widgets[caller].isChecked())

    def chbox_sendkeys_changed(self):
        """Toggle sending keyboard events"""
        self.sendkeys = self.mb_widgets['sendkeys'].isChecked()

    def btn_loadcfg_click(self):
        """Load saved configuration parameters."""
        # caller = 'loadcfg'
        raise NotImplementedError('more work to do')

    def btn_keycfg_click(self):
        """Open key press config window/dialog."""
        # caller = 'loadcfg'
        self.keyselect.exec_()
        # raise NotImplementedError('more work to do')

    def btn_cal_click(self):
        """Perform calibration.

        Feature unfinished.
        """
        caller = 'cal'
        if not self.docalibration:
            self.docalibration = True
            self.mb_widgets[caller].setText('click to cancel calibration')
            disable_list = self.mb_widgets.values()
            disable_list.remove(self.mb_widgets[caller])
            self.disable_widgets(disable_list)
            self.calibration_handler()
        else:
            self._btn_cal_reset()
            self.calibration_handler()

    def _btn_cal_reset(self):
        """Reset calibration dialog."""
        caller = 'cal'
        self.docalibration = False
        self.mb_widgets[caller].setText('click to calibrate')
        self.enable_widgets(self.mb_widgets.values())
        self.cfg['handler'].do_polling = False
        self.cfg['handler'].nowrite = not self.mb_widgets[caller].isChecked()

    def disable_widgets(self, widgets):
        """Disable every widget in a list of widgets."""
        for w in widgets:
            # self.mb_widgets[w].setEnabled(False)
            w.setEnabled(False)
        app.processEvents()

    def enable_widgets(self, widgets):
        """Enable every widget in a list of widgets."""
        for w in widgets:
            # self.mb_widgets[w].setEnabled(True)
            w.setEnabled(True)
        app.processEvents()

    def calibration_handler(self):
        """Calibration handler."""
        if self.docalibration:
            self.cfg['handler'].do_polling = True
            self.cfg['handler'].nowrite = False

            print 'doing calibration'
            self.cal_thread = threading.Timer(float(self.datalen / self.cfg['sampfreq']),
                                              self.calibrator.on_show)
            self.cal_thread.start()
            self.calibrator.exec_()
        else:
            if self.cal_thread:
                self.cal_thread.cancel()
                print 'calibration cancelled'
                self._btn_cal_reset()
        return

    def _cal_timeout(self):
        print 'timeout!'
        self._btn_cal_reset()
        return


# unimplemented
class calDialog(QtGui.QDialog):
    """A dialog window for instructing the user through calibration.

    Not yet implemented properly. Unfinished.
    """

    def __init__(self, cfg, parent=None):
        """Constructor.

        Window to appear when calibration is activated.
        cfg parameters:
            'cal_patterns' - list of lists of channel names
            'cal_repeats' - # of times to repeat each pattern
            'cal_onofftime' - tuple or list e.g. [1., 2.] - number of seconds on and off

            Labels:
                One for overview + instructions
                One large one for flashing 'tense/release'
                One set for telling the user which channels to activate
            Buttons:
                Start/next/OK button
                Cancel button
                ?? Reset button ?? - cancel & restart current pattern

            Internal things:
                Have a thing which outputs to a calibration file OR memory
                    ---NEEDS to hook into IO_handler functions
                csv format: x[0], ch03dp, x[1], ch13dp, x[2], ch23dp, x[3], ch33dp,
                    where x is an array of containing each channel's activation state
        """
        self.parent = parent
        super(calDialog, self).__init__(parent.mainwin)
        self.pattern_idx = 0
        self.patterns = cfg['cal']
        self.repeats = cfg['calcfg']['repeats']
        self.on_time = cfg['calcfg']['intervals'][0]
        self.off_time = cfg['calcfg']['intervals'][1]

        self.instruction_strings = ['Press \'Ok\' to start calibrating pattern: ',
                                    'Calibrating ',
                                    'Done. Click \'Ok\' to exit.']
        self.prompt_strings = ['Your instructions will appear here.',
                               'TENSE ({} sec) '.format(self.on_time),
                               'RELEASE ({} sec) '.format(self.off_time)]

        title = QtGui.QLabel('EMG CALIBRATION')

        self.textBox = QtGui.QTextEdit(self)
        self.textBox.setReadOnly(True)
        self.textBox.append("Patterns to calibrate:")
        for pattern in self.patterns:
            box_str = 'Pulse: {}'.format(str(pattern.cued))
            if pattern.static:
                box_str += ', hold: '
                for static in pattern.static:
                    box_str += '{}, '.format(str(static))
            self.textBox.append(box_str)
        self.textBox.append('End.')
        self.textBox.moveCursor(QtGui.QTextCursor.Start,
                                QtGui.QTextCursor.MoveAnchor)
        self.textBox.moveCursor(QtGui.QTextCursor.EndOfLine,
                                QtGui.QTextCursor.KeepAnchor)

        self.instructions = QtGui.QLabel('purging queue')
        self.prompt = QtGui.QLabel('Please wait...')

        self.buttonBox = QtGui.QDialogButtonBox(self)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)

        self.verticalLayout = QtGui.QVBoxLayout(self)
        self.verticalLayout.addWidget(title)
        self.verticalLayout.addSpacing(1)
        self.verticalLayout.addWidget(self.textBox)
        self.verticalLayout.addSpacing(1)
        self.verticalLayout.addWidget(self.instructions)
        self.verticalLayout.addWidget(self.prompt)
        self.verticalLayout.addSpacing(2)
        self.verticalLayout.addWidget(self.buttonBox)
        self.buttonBox.accepted.connect(self.btn_ok_click)
        self.buttonBox.rejected.connect(self.btn_cancel_click)
        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(False)

        self.cfg = cfg
        self.tests ={}
        for ID in cfg['indices']:
            # self.tests[ID] = cfg['indices'][ID] % 2
            self.tests[ID] = 0
        # self.show()

    def on_show(self):
        """Activate buttons and labels appropriately.

        Should be called in a timer thread straight after QDialog exec.
        Timeout should be long enough to flush entire queue.
        = datalen / sampfreq"""
        self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(True)
        self.instructions.setText(self.instruction_strings[0] + str(self.patterns[self.pattern_idx].cued))
        self.prompt.setText(self.prompt_strings[0])
        self.move_box_selection(self.textBox)
        return

    def btn_cancel_click(self):
        self.parent.btn_cal_click()
        self.reject()

    def btn_ok_click(self):
        print 'ok clicked'
        if self.pattern_idx < len(self.patterns):
            # self.tests = {}
            repeat_count = 0
            prompt_end = '/' + str(self.repeats)
            curr_pattern = self.patterns[self.pattern_idx]
            self.move_box_selection(self.textBox)
            self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(False)
            if curr_pattern.static:
                instruct_text = self.instruction_strings[1] + str(curr_pattern.cued) + ', holding ' + str(curr_pattern.static)
            else:
                instruct_text = self.instruction_strings[1] + str(curr_pattern.cued)
            self.instructions.setText(instruct_text)
            app.processEvents()
            for ID in self.cfg['indices']:
                if ID in curr_pattern.cued:
                    print 'cueing' + ID + ', ',
                if ID in curr_pattern.static:
                    self.tests[ID] = 1
                    print 'holding ' + ID + ', ',
                else:
                    self.tests[ID] = 0
            print ''
            # time.sleep(self.on_time)
            # print ' ...release! test {}/{}'.format(self.pattern_idx + 1,
            #                                        len(self.patterns))
            # time.sleep(self.off_time)
            while repeat_count < self.repeats:
                repeat_count += 1
                # tense target/s
                self.prompt.setText(self.prompt_strings[1] + str(repeat_count) + prompt_end)
                for ID in curr_pattern.cued:
                    self.tests[ID] = 1
                app.processEvents()
                time.sleep(self.on_time)
                # release target/s
                self.prompt.setText(self.prompt_strings[2] + str(repeat_count) + prompt_end)
                for ID in curr_pattern.cued:
                    self.tests[ID] = 0
                app.processEvents()
                time.sleep(self.off_time)

            for key in self.tests:
                self.tests[key] = 0
            print 'click ok to do next test'
            self.buttonBox.button(QtGui.QDialogButtonBox.Ok).setEnabled(True)
            self.pattern_idx += 1
            if self.pattern_idx < len(self.patterns):
                curr_pattern = self.patterns[self.pattern_idx]
                if curr_pattern.static:
                    instruct_text = self.instruction_strings[0] + str(curr_pattern.cued) + ', holding ' + str(curr_pattern.static)
                else:
                    instruct_text = self.instruction_strings[0] + str(curr_pattern.cued)
                self.instructions.setText(instruct_text)
                self.prompt.setText(self.prompt_strings[0])
            else:
                self.instructions.setText(self.instruction_strings[2])
                self.prompt.setText('')
        else:
            self.parent.btn_cal_click()
            self.accept()

    def move_box_selection(self, box):
        box.moveCursor(QtGui.QTextCursor.StartOfLine, QtGui.QTextCursor.MoveAnchor)
        box.moveCursor(QtGui.QTextCursor.Down, QtGui.QTextCursor.MoveAnchor)
        box.moveCursor(QtGui.QTextCursor.EndOfLine, QtGui.QTextCursor.KeepAnchor)


class keysDialog(QtGui.QDialog):
    """A dialog window for allowing user to set EMG channel combos & keys."""

    def __init__(self, cfg, parent=None):
        """Constructor.

        Window to appear when 'configure keys' is clicked.
        cfg parameters:


            Labels:
                One for overview + instructions
            Buttons:
                OK button - commit new config
                Cancel button - keep prev config

            Internal things:

        """
        self.parent = parent
        super(keysDialog, self).__init__(parent.mainwin)
        title = QtGui.QLabel('Key Configuration:\n(checked=must be active, cleared=must be inactive, other=dontcare)')

        # num_keys controls the number of key selectors
        num_keys = 4  # needs to be stored and loaded from cfg

        # add button controls and descriptive labels
        self.buttonBox = QtGui.QDialogButtonBox(self)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)

        self.selectionGrid = QtGui.QGridLayout(self)
        self.selectionGrid.addWidget(title, 0, 0, 1, -1)

        labels = QtGui.QHBoxLayout(self)
        labels.addWidget(QtGui.QLabel('Key:'), 0, 68)
        labels.addSpacing(2)
        labels.addWidget(QtGui.QLabel('Action:'), 0, 130)
        self.selectionGrid.addLayout(labels, 1, 0, 1, 3)

        # for each channel, create an empty list for checkboxes and store in a dict
        self.chanBoxes = {}
        verticals = {'keys': QtGui.QVBoxLayout(self)}  # also create a dict for all the columns
        for name in cfg['names']:
            self.chanBoxes[name] = []
            verticals[name] = QtGui.QVBoxLayout(self)  # add a column for the channel
            verticals[name].addWidget(QtGui.QLabel(cfg['names'][name]), 1, 4)

        # populate a list with comboboxes
        self.keySelectors = []
        for i in range(num_keys):
            parent.combo_map.append({})
            parent.selected_keys.append(None)
            this_key = QtGui.QComboBox(self)
            this_key.addItem('Select Key...', None)
            for keyname in cfg['keys']:
                this_key.addItem(keyname, cfg['keys'][keyname])
            self.keySelectors.append(this_key)
            verticals['keys'].addWidget(this_key)
            # also for every combobox add a checkbox to each channel's checkboxlist
            for name in cfg['names']:
                cb = QtGui.QCheckBox(self)
                cb.setTristate(True)  # make it a three-way
                cb.setCheckState(QtCore.Qt.CheckState.PartiallyChecked)
                verticals[name].addWidget(cb, 1, 4) # add it to the column
                self.chanBoxes[name].append(cb)  # add it the the checkboxlist
                # set the default combo_map value
                parent.combo_map[i][name] = QtCore.Qt.CheckState.PartiallyChecked

        self.selectionGrid.addLayout(verticals['keys'], 4, 0, num_keys, 1)
        i = 2
        for name in cfg['names']:
            self.selectionGrid.addLayout(verticals[name], 2, i, (1 + num_keys), 1)
            self.selectionGrid.setColumnMinimumWidth(i, 96)
            self.selectionGrid.setColumnStretch(i, 1)
            i += 1

        self.selectionGrid.addWidget(self.buttonBox, 8, 0, 1, -1, 4)
        self.selectionGrid.setColumnMinimumWidth(1, 32)
        self.selectionGrid.setRowMinimumHeight(2, 48)

        self.buttonBox.accepted.connect(self.btn_ok_click)
        self.buttonBox.rejected.connect(self.btn_cancel_click)

        self.cfg = cfg

    def btn_cancel_click(self):
        # discard changes, revert checkboxes and key selectors to stored state
        p = self.parent
        for i in range(0, len(p.combo_map)):
            cBoxIndex = self.keySelectors[i].findData(p.selected_keys[i])
            if cBoxIndex == -1:
                cBoxIndex = 0
            self.keySelectors[i].setCurrentIndex(cBoxIndex)
            for name in p.cfg['names']:
                self.chanBoxes[name][i].setCheckState(p.combo_map[i][name])
        self.reject()

    def btn_ok_click(self):
        # save checkbox states in parent.combo_map
        p = self.parent
        for i in range(0, len(p.combo_map)):
            p.selected_keys[i] = self.keySelectors[i].itemData(self.keySelectors[i].currentIndex())
            for name in p.cfg['names']:
                p.combo_map[i][name] = self.chanBoxes[name][i].checkState()
        self.accept()


class Channel(object):
    """A class for DSP and plotting related functions."""

    def __init__(self, ID, cfg):
        """Basic constructor.

        Takes parameters:
        ID: string identifying the muscle attached to this channel.
        index: int specifying where this channel is in the parsed_data array
        cfg: the 'config' dict containing global constants.
        """
        self.cfg = cfg
        if self.cfg['raw_output']:
            print 'outputting raw'
        self.raw_Q = deque([0.0] * cfg['datalen'], cfg['datalen'])
        self.datalen = cfg['datalen']
        self.ID = ID
        self.idx = cfg['indices'][ID]
        self.sampfreq = cfg['sampfreq']
        self.plotwin = cfg['win']
        self.read_data = []
        self.read_diff = 0
        # Thread control
        self.read_trigger = False
        self.terminated = False
        self.fftcounter = 0
        # DSP setup
        stop = cfg['mainsfreq'] + cfg['notch_width'] * np.array([-1., 1.])
        b_AC1, a_AC1 = signal.butter(cfg['filt_order'],
                                     stop/(self.sampfreq / 2.0),
                                     'bandstop')  # create the mains filter

        stop = .5 * cfg['mainsfreq'] + cfg['notch_width'] * np.array([-1., 1.])
        b_AC2, a_AC2 = signal.butter(cfg['filt_order'],
                                     stop/(self.sampfreq / 2.0),
                                     'bandstop')  # create the mains/2 filter

        # stop = 2. * cfg['mainsfreq'] + cfg['notch_width'] * np.array([-1., 1.])
        # b_AC3, a_AC3 = signal.butter(cfg['filt_order'],
        #                              stop/(self.sampfreq / 2.0),
        #                              'bandstop')  # create the 2*mains filter

        # convolve all filter coefficients to yield combined filter
        self.a = np.convolve(a_AC2, a_AC1)
        # self.a = np.convolve(np.convolve(a_AC2, a_AC1), a_AC3)
        self.b = np.convolve(b_AC2, b_AC1)
        # self.b = np.convolve(np.convolve(b_AC2, b_AC1), b_AC3)
        self.filtlen = max(len(self.a), len(self.b))

    def read_in(self):
        """Checks for missed packets, then calls dsp() as required."""
        while not self.terminated:  # run forever!
            if self.read_trigger:  # check for trigger
                self.read_trigger = False
                data = self.read_data
                diff = self.read_diff
                newVal = float(data[self.idx])
                if diff != 1:
                    # interpolation routine
                    nextVal = self.raw_Q[0]
                    delta = (newVal - nextVal) / diff
                    print diff
                    for _ in xrange(0, diff):
                        nextVal += delta
                        self.dsp(nextVal)
                else:
                    self.dsp(newVal)
        print '{} channel thread terminating...'.format(self.ID)
        return

    def dsp(self, newVal):
        """Performs the actual signal processing.

        50Hz  notch filter (Butterworth).
        100Hz notch filter (Butterworth). <-- actually 25 Hz
        """
        self.raw_Q.appendleft(newVal)

        if self.cfg['raw_output'] == True:
            self.plotwin.data[self.ID].appendleft(float(newVal))
            # if self.ID == 'R_AS':
            #     print newVal
            return

        # #### ==== FILTER MATH ==== ####
        # We've already computed the two coefficient vectors a and b.
        # If N is the length of b, and M is the length of a,
        # and x is the input vector, and y is the output vector,
        # and x[0] is the most recent input, and y[0] is the most recent output
        # (which we haven't yet calculated) then:
        #
        #     a[0]*y[0] + a[1]*y[1] + ... + a[M-1]*y[M-1]
        #       == b[0]*x[0] + b[1]*x[1] + ... + b[N-1]*x[N-1]
        #
        #
        # rearranging for y[0]:
        #
        #     y[0] == ( (b[0]*x[0] + b[1]*x[1] + ... + b[N-1]*x[N-1])
        #             - (a[1]*y[1] + ... + a[M-1]*y[M-1]) ) / a[0]

        # filtX = np.array([newVal], np.float)  # x[0] is the latest raw value
        # for i in range(1, len(self.b)):  # fill filtX with raw data values
        #     filtX = np.append(filtX, np.array(self.raw_Q[i], np.float))
        #
        # filtY = np.array([0], np.float)  # y[0] is 0 so that a[0]*y[0] is ignored
        # for i in range(1, len(self.a)):  # fill filtY with past output values
        #     filtY = np.append(filtY, np.array(self.plotwin.data[self.ID][i-1],
        #                                       np.float))

        filtX = np.fromiter(self.raw_Q, np.float, self.filtlen)
        filtY = np.append([0.], np.fromiter(self.plotwin.data[self.ID],
                                            np.float, self.filtlen - 1))

        # calculate y[0]
        out = (self.b.dot(filtX) - self.a.dot(filtY)) / self.a[0]
        self.plotwin.data[self.ID].appendleft(out)  # append y[0] to the filtered data queue

        if self.fftcounter >= self.plotwin.fftcount:
            self.fftcounter = 0
            self.plotwin.ffts[self.ID] = self.short_fft()
        else:
            self.fftcounter += 1

        # delete function variables... just in case
        del filtX
        del filtY
        return out

    def short_fft(self):
        """Return the real-fft value of this channel's data queue."""
        # front = np.fromiter(self.plotwin.data[self.ID], np.float)[:self.plotwin.fftlen]
        # return np.abs(np.fft.rfft(front))
        iter_tmp = np.fromiter(self.plotwin.data[self.ID], np.float)
        return np.abs(np.fft.rfft(iter_tmp[:self.plotwin.fftlen]))[1:]


class IO_handler(object):
    """Handler for I/O."""

    def __init__(self, port, bauds, channels, nowrite=True):
        try:
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = bauds
            ser.open()
            print 'connect success!'
            self.ser = ser
            self.channels = channels
            self.do_polling = False
            self.kill_thread = False
            self.dsp_threads = []
            self.nowrite = nowrite
            for ch in channels:
                dsp_thread = Thread(target=ch.read_in, args=())
                self.dsp_threads.append(dsp_thread)
                ch.terminated = False
                ch.read_trigger = False
                dsp_thread.start()
        except (OSError, serial.SerialException):
            print 'Error opening serial port: ' + port
            exit(2)

    def poll_serial(self):
        """Monstrous function to handle serial comms and data output."""
        while not self.kill_thread:  # superloop
            if self.ser.is_open and self.do_polling:
                # this only runs once when do_polling becomes true
                DO_ONCE = True
                nowrite = self.nowrite
                cfg = self.channels[0].cfg
                docalibration = cfg['win'].docalibration
                # self.init_chans()
                if not nowrite:
                    output, filename = self._open_output_file(docalibration)
                # initialize counter and header check bytes
                samples = 0
                h = 'cc'  # header value --- 0xFC
                h1 = ''
                h2 = ''
                self.ser.reset_input_buffer()  # purge buffer
                while self.ser.is_open and self.do_polling:  # superloop in a superloop
                    if self.ser.in_waiting:  # data available
                        h2 = self.ser.read().encode('hex')  # read it
                        if (h2 == h) and (h1 == h):  # check if got both headers
                            samples += 1
                            h1 = ''
                            raw_data = self.ser.read(7)  # read the rest
                            parsed_data = self._parse_raw(raw_data)  # parse it
                            if not nowrite and not docalibration:  # write it
                                output_line = self._format_output(parsed_data)
                                output.write(output_line)
                            else:  # something to do with docalibration
                                output_line = '{},{},'.format(parsed_data[0],
                                                              parsed_data[1])

                            # on first sample, force diff to 1
                            if DO_ONCE:
                                prev_count = parsed_data[1] - 1
                                diff = 1
                                DO_ONCE = False
                            else:
                                diff = (parsed_data[1] - prev_count + 256) % 256
                                prev_count = parsed_data[1]

                            # iterate over channels, trigger read_in
                            for ch in self.channels:
                                if docalibration:
                                    filt = cfg['win'].data[ch.ID][0]
                                    cal = cfg['win'].calibrator.tests[ch.ID]
                                    output_line += '{0:.0f},{1:.2f},{2},'.format(ch.raw_Q[0],
                                                                                 filt,
                                                                                 cal)
                                ch.read_data = parsed_data
                                ch.read_diff = diff
                                ch.read_trigger = True
                                # end for

                            if docalibration:  # add newline if calibrating
                                output_line += '\n'
                                output.write(output_line)
                        else:  # didn't get both headers. Try again.
                            h1 = h2
                if not nowrite:
                    # clean up (stream stop) - close output file
                    print "Recorded {} samples to {}".format(samples, filename)
                    if not output.closed:
                        output.close()
            else:
                # flush serial buffer & sleep half a second
                self.ser.reset_input_buffer()
                time.sleep(0.5)

        # clean up (exit) - stop DSP threads and close serial port
        if self.ser.is_open:
            self.ser.close()
        for ch in self.channels:
            ch.terminated = True
        return

    def _parse_raw(self, raw_data):
        """Parse the data packet. Does a lot of bit-shifting."""
        return [ord(raw_data[0]), ord(raw_data[1]),
                ((ord(raw_data[6]) & 3) << 8) + ord(raw_data[2]),
                ((ord(raw_data[6]) & 12) << 6) + ord(raw_data[3]),
                ((ord(raw_data[6]) & 48) << 4) + ord(raw_data[4]),
                ((ord(raw_data[6]) & 192) << 2) + ord(raw_data[5])]

    def _format_output(self, parsed_data):
        return "{},{},{},{},{},{}\n".format(parsed_data[0],
                                            parsed_data[1],
                                            parsed_data[2],
                                            parsed_data[3],
                                            parsed_data[4],
                                            parsed_data[5])

    def _open_output_file(self, docalibration):
        filename = datetime.datetime.now().strftime("data_%Y-%m-%d_%H%M-%S") + ".csv"
        if docalibration:
            filename = 'calibration_' + filename
        filename = './data/' + filename
        try:
            output = open(filename, 'w')
        except (OSError, IOError):
            print 'Error opening file: {}'.format(filename)
            exit(2)
        else:
            if not docalibration:
                output.write("RAW DATA ONLY\nOCRval,count,Ch0,Ch1,Ch2,Ch3\n")
            else:
                # sorted(channels, key=lambda ch: ch.idx)
                # output.write("Columns\nOCRval,count,Ch0,Ch1,Ch2,Ch3\n")
                header_line = "Columns\n,,"
                line2 = '\nOCRval,count,'
                for ch in self.channels:
                    header_line += 'Ch{} ({}),,,'.format(ch.idx-2, ch.ID)
                    line2 += 'raw,filt,cal,'
                line2 += '\n'
                header_line += line2
                output.write(header_line)
        return output, filename

    # def init_chans(self):
    #     for ch in self.channels:
    #         dsp_thread = Thread(target=ch.read_in, args=())
    #         self.dsp_threads.append(dsp_thread)
    #         ch.terminated = False
    #         ch.read_trigger = False
    #         dsp_thread.start()
    #     return
