"""A library for the various object classes used in olimex-emg-read.py.

blah.
"""

from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import numpy as np
from scipy import signal
from collections import deque
from threading import Thread
import serial
import datetime
import time
from functools import partial

app = QtGui.QApplication([])

def runningMeanFast(x, N):
    return np.convolve(x, np.ones((N,))/N)[(N-1):]

class DisplayWindow(object):
    """A generic wrapper for our QtGui window.

    Will contain all the functions for the plotting and data output.
    """

    def __init__(self, cfg):
        """Constructor."""
        self.cfg = cfg  # store config info
        self.mainwin = QtGui.QMainWindow()
        self.mainwin.setWindowTitle(cfg['title'])
        self.mainwin.resize(cfg['width'], cfg['height'])
        self.central_widget = QtGui.QWidget()
        self.mainwin.setCentralWidget(self.central_widget)
        self.maincontrolbar = {'layout': QtGui.QVBoxLayout()}
        self.top_layout = QtGui.QHBoxLayout()
        self.side_layouts = {'left': QtGui.QVBoxLayout(),
                             'right': QtGui.QVBoxLayout()}
        self.top_layout.addLayout(self.side_layouts['left'])
        self.top_layout.addLayout(self.side_layouts['right'])
        self.top_layout.addLayout(self.maincontrolbar['layout'])
        self.central_widget.setLayout(self.top_layout)

        # maincontrolbar setup
        self.maincontrolbar['streamctl'] = QtGui.QPushButton('Start streaming')
        self.maincontrolbar['streamctl'].clicked.connect(self.btn_streamctl_click)
        self.maincontrolbar['layout'].addWidget(self.maincontrolbar['streamctl'])
        self.maincontrolbar['layout'].addSpacing(1)
        self.maincontrolbar['loadcfg'] = QtGui.QPushButton('Load config')
        self.maincontrolbar['layout'].addWidget(self.maincontrolbar['loadcfg'])
        self.maincontrolbar['cal'] = QtGui.QPushButton('Calibrate')
        self.maincontrolbar['layout'].addWidget(self.maincontrolbar['cal'])
        self.maincontrolbar['layout'].addStretch(1)


        self.plot_timer = QtCore.QTimer()
        self.plot_timer.timeout.connect(self.update_plots)
        plot_names = cfg['plot_names']
        self.plot_names = plot_names
        plot_colours = {2: (255, 111, 055),
                        3: (055, 111, 255),
                        4: (255, 99, 111),
                        5: (111, 99, 255)}

        self.plotwidgets = {}
        self.plotcontrols = {}
        self.plots = {}
        self.datalen = 4 * cfg['sampfreq']
        self.data = {}
        self.detect_time = {}

        for plt in plot_names:
            self.plotwidgets[plt] = pg.PlotWidget(name=plt)
            bar = {}
            bar['tlabel'] = QtGui.QLabel('Threshold: ')
            bar['tctlbox'] = QtGui.QSpinBox()
            bar['tctlbox'].setRange(0, 1023)
            bar['tctlbox'].setSingleStep(1)
            bar['tctlbox'].setSuffix(' counts')
            bar['tctlbox'].setValue(512)
            # bar['tctlbox'].valueChanged.connect(lambda: self.threshold_changed(plt))
            # bar['tctlbox'].valueChanged.connect(partial(self.threshold_changed, plt))
            # self.thresholds[plt] = 512
            bar['detected'] = QtGui.QLabel('DETECT', )
            bar['layout'] = QtGui.QHBoxLayout()
            bar['layout'].addWidget(bar['tlabel'])
            bar['layout'].addWidget(bar['tctlbox'])
            bar['layout'].addWidget(bar['detected'])
            self.detect_time[plt] = 0.0
            bar['hbox'] = QtGui.QGroupBox('Channel {} controls'.format(plt))
            bar['hbox'].setLayout(bar['layout'])
            self.plotcontrols[plt] = bar
            self.plots[plt] = self.plotwidgets[plt].plot()
            self.plots[plt].setPen(plot_colours[cfg['indices'][plt]])
            if plt.startswith('L'):
                self.side_layouts['left'].addWidget(self.plotwidgets[plt])
                self.side_layouts['left'].addWidget(bar['hbox'])
            elif plt.startswith('R'):
                self.side_layouts['right'].addWidget(self.plotwidgets[plt])
                self.side_layouts['right'].addWidget(bar['hbox'])

            self.data[plt] = deque([0.0]*self.datalen, self.datalen)

        for i in xrange(0, self.datalen):
            for plt in plot_names:
                self.data[plt].appendleft(np.sin(i/10.))
                if i == self.datalen - 1:
                    self.plots[plt].setData(self.data[plt])

        self.plot_timer.start(cfg['plot_timer_ms'])
        self.mainwin.show()

    def update_plots(self):
        title_string = self.cfg['title']
        for plt in self.plot_names:
            threshold = self.plotcontrols[plt]['tctlbox'].value()
            self.plots[plt].setData(self.data[plt])
            title_string += ' | {0} p-p : {1:.0f}'.format(plt,
                                                    np.amax(self.data[plt]) - np.amin(self.data[plt]))
            # if  time.time() > self.detect_time[plt]:
            if np.amax(np.fromiter(self.data[plt], np.float, 64)) > threshold:
                # self.detect_time[plt] = time.time() + 0.25
                self.plotcontrols[plt]['detected'].setText('DETECT')
                # print np.amax(self.data[plt])
            else:
                self.plotcontrols[plt]['detected'].setText('none')
        self.mainwin.setWindowTitle(title_string)
        app.processEvents()

    # def threshold_changed(self, chname):
    #     print chname
    #     self.thresholds[chname] = self.plotcontrols[chname]['tctlbox'].value()

    def btn_streamctl_click(self):
        if self.cfg['handler'].do_polling:
            self.cfg['handler'].do_polling = False
            self.maincontrolbar['streamctl'].setText('Start streaming')
            self.clear_plots()
        else:
            self.cfg['handler'].do_polling = True
            self.maincontrolbar['streamctl'].setText('Stop streaming')

    def clear_plots(self):
        for plt in self.plot_names:
            q = self.data[plt]
            flatline = q[0]
            for _ in xrange(0, self.datalen):
                q.appendleft(flatline)
        return



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
        # DSP setup
        stop = cfg['mainsfreq'] + cfg['notch_width'] * np.array([-1., 1.])
        b_AC1, a_AC1 = signal.butter(cfg['filt_order'],
                                     stop/(self.sampfreq / 2.0),
                                     'bandstop')  # create the mains filter

        stop = 2. * cfg['mainsfreq'] + cfg['notch_width'] * np.array([-1., 1.])
        b_AC2, a_AC2 = signal.butter(cfg['filt_order'],
                                     stop/(self.sampfreq / 2.0),
                                     'bandstop')  # create the 2*mains filter

        # convolve all filter coefficients to yield combined filter
        self.a = np.convolve(a_AC2, a_AC1)
        self.b = np.convolve(b_AC2, b_AC1)
        self.filtlen = max(len(self.a), len(self.b))

    def read_in(self):
        """Checks for missed packets, then calls dsp() as required."""
        while not self.terminated:
            if self.read_trigger:
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
        100Hz notch filter (Butterworth).
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
        out = self.b.dot(filtX) - self.a.dot(filtY) / self.a[0]
        self.plotwin.data[self.ID].appendleft(out)  # append y[0] to the filtered data queue

        # delete function variables... just in case
        del filtX
        del filtY
        return out


class IO_handler(object):
    """Handler for I/O."""

    def __init__(self, port, bauds, channels, nowrite=False):
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
        while not self.kill_thread:
            if self.ser.is_open and self.do_polling:
                DO_ONCE = True
                # self.init_chans()
                if not self.nowrite:
                    filename = datetime.datetime.now().strftime("data_%Y-%m-%d_%H%M-%S") + ".csv"
                    try:
                        output = open(filename, 'w')
                    except (OSError, IOError):
                        print 'Error opening file: {}'.format(filename)
                        exit(2)
                    else:
                        output.write("RAW DATA ONLY\nOCRval,count,Ch0,Ch1,Ch2,Ch3\n")
                samples = 0
                h = 'cc'  # header value --- 0xFC
                h1 = ''
                h2 = ''
                self.ser.reset_input_buffer()
                while self.ser.is_open and self.do_polling:
                    if self.ser.in_waiting:
                        h2 = self.ser.read().encode('hex')
                        if (h2 == h) and (h1 == h):
                            h1 = ''
                            raw_data = self.ser.read(7)
                            # parsed_data = [ord(raw_data[0]),
                            #                ord(raw_data[1]),
                            #                (ord(raw_data[2]) << 8) + ord(raw_data[3]),
                            #                (ord(raw_data[4]) << 8) + ord(raw_data[5]),
                            #                (ord(raw_data[6]) << 8) + ord(raw_data[7]),
                            #                (ord(raw_data[8]) << 8) + ord(raw_data[9])]
                            parsed_data = [ord(raw_data[0]),
                                           ord(raw_data[1]),
                                           ((ord(raw_data[6]) & 3) << 8) + ord(raw_data[2]),
                                           ((ord(raw_data[6]) & 12) << 6) + ord(raw_data[3]),
                                           ((ord(raw_data[6]) & 48) << 4) + ord(raw_data[4]),
                                           ((ord(raw_data[6]) & 192) << 2) + ord(raw_data[5])]
                            if not self.nowrite:
                                output_line = "{},{},{},{},{},{}\n".format(parsed_data[0],
                                                                           parsed_data[1],
                                                                           parsed_data[2],
                                                                           parsed_data[3],
                                                                           parsed_data[4],
                                                                           parsed_data[5])
                                output.write(output_line)
                            samples += 1
                            if DO_ONCE:
                                prev_count = parsed_data[1] - 1
                                DO_ONCE = False
                            diff = (parsed_data[1] - prev_count + 256) % 256
                            prev_count = parsed_data[1]
                            diff = 1
                            # threads = []
                            for ch in self.channels:
                                ch.read_data = parsed_data
                                ch.read_diff = diff
                                ch.read_trigger = True
                                # dsp_thread = Thread(target=ch.read_in,
                                #                     args=(parsed_data, diff))
                                # threads.append(dsp_thread)
                                # dsp_thread.start()
                            # for t in threads:
                            #     t.join()
                        else:
                            h1 = h2
                if not self.nowrite:
                    print "Recorded {} samples to {}".format(samples, filename)
                    if not output.closed:
                        output.close()
            else:
                # pass
                self.ser.reset_input_buffer()


        if self.ser.is_open:
            self.ser.close()
        for ch in self.channels:
            ch.terminated = True
        return

    # def init_chans(self):
    #     for ch in self.channels:
    #         dsp_thread = Thread(target=ch.read_in, args=())
    #         self.dsp_threads.append(dsp_thread)
    #         ch.terminated = False
    #         ch.read_trigger = False
    #         dsp_thread.start()
    #     return
