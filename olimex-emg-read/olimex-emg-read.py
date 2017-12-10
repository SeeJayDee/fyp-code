# === olimex-emg-read.py ===
# * Function: to set golbal variables and execute the main program.
# *
# * This is part of Christian D'Abrera's engineering final
# * year project titled "EMG Bio-feedback for rehabilitation".
# *
# * Christian D'Abrera
# * Curtin University 2017
# * christian.dabrera@student.curtin.edu.au
# * chrisdabrera@gmail.com

# REPLACE SERIAL PORT FINDER WITH INBUILT FUNCTION
# "python -m serial.tools.list_ports"

from pyqtgraph.Qt import QtGui, QtCore
import os
import sys
import glob
import serial
import argparse
from threading import Thread
from time import sleep
import classes as c
# import spaceinvaders as game

# #### GLOBAL VARIABLES ####
parser = argparse.ArgumentParser()
parser.add_argument("port", help="the name of the serial \
                                  port, ie \'COM3\' or \'/dev/ttyS0\'")
parser.add_argument("-b", "--baudrate",
                    help="the serial baud rate, ie 19200, 57600, 115200",
                    type=int, default=115200)
parser.add_argument("-N", "--nowrite", action="store_true")  # deprecated
parser.add_argument("-R", "--raw_output", action="store_true")

# global parameters dict
config = {'sampfreq': 256,  # sample freq, Hz
          'datalen': 4096,  # data queue length
          'mainsfreq': 50,  # local mains freq, Hz
          'notch_width': 0.5,  # notch filter bandwidth, Hz
          'filt_order': 3,  # notch filter order
          'raw_output': False,
          'title': 'EMG Grapher',  # window title
          'width': 1280,  # window width
          'height': 800,  # window height
          'plot_timer_ms': 50,  # plot update interval, ms
          'plot_names': ['th_add', 'th_abd', 'fi_flx', 'fi_ext'],
          'indices': {'th_add': 5,  # index of chan's data in packet
                      'th_abd': 4,
                      'fi_flx': 3,
                      'fi_ext': 2},
          'names': {'th_add': 'ADduct Thumb',  # description of channel
                    'th_abd': 'ABduct Thumb',
                    'fi_flx': 'Flex Fingers',
                    'fi_ext': 'Extend Fingers'},
          'keys': None}

prefixes = ['th', 'fi']  # plot name prefixes

# part of unimplemented calibration functionality
calcfg = {'repeats': 5,
    #    'intervals': [.1, .2]}
       'intervals': [1., 2.]}
config['calcfg'] = calcfg


def populate_patterns(prefix_list, cal_cfg):
    """ 'Populate calibration patterns'
    Part of unimplemented feature to record EMG data while the user was asked
    to follow a particular movement 'pattern'.
    """
    cal_patterns = []
    mgroups = sorted(config['plot_names'])
    for m in mgroups:  # populate patterns for isolated channels FIRST
        cal_patterns.append(c.cal_pattern(cal_cfg['repeats'],
                                          [m],
                                          [],
                                          cal_cfg['intervals']))
    for m in mgroups:  # populate combined patterns
        grp = ''
        for pre in prefix_list:  # note muscle group
            if m.startswith(pre):
                grp = pre
                break
        for o in mgroups:  # iterate over groups again
            if o.startswith(grp):
                continue
            cal_patterns.append(c.cal_pattern(cal_cfg['repeats'],
                                              [m],
                                              [o],
                                              cal_cfg['intervals']))
    return cal_patterns


def serial_ports():
    """ Lists serial port names.

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if os.name == 'nt':  # sys.platform == 'win32':
        from serial.tools.list_ports_windows import comports
    elif os.name == 'posix':
        from serial.tools.list_ports_posix import comports
    # ~ elif os.name == 'java':
    else:
        raise ImportError("Sorry: no implementation for your platform \
                          ('{}') available".format(os.name))

    result = []
    for (p, _, _) in sorted(comports()):
        result.append(p)
    return result


def _main():
    global config
    args = parser.parse_args()
    if args.port in serial_ports():
        if args.raw_output:  # set raw output flag
            config['raw_output'] = True
        channels = []
        config['cal'] = populate_patterns(prefixes, calcfg)  # unimplemented
        # declare main window
        config['win'] = c.DisplayWindow(config)
        # declare Channels
        for chname in config['plot_names']:
            channels.append(c.Channel(chname, config))
        # ensure channel list is in correct order for data packet
        channels = sorted(channels, key=lambda ch: ch.idx)
        # declare I/O handler
        config['handler'] = c.IO_handler(args.port, args.baudrate, channels)
        config['poller'] = Thread(target=config['handler'].poll_serial, args=())
        config['poller'].start()
        # import objgraph
        # objgraph.show_refs([config['win']], filename='win_refs.png')
        # objgraph.show_refs([config['handler']], filename='io_refs.png')
        # objgraph.show_refs([channels[0]], filename='chan_refs.png')
        # objgraph.show_backrefs([config['win']], filename='win_Brefs.png')
        # objgraph.show_backrefs([config['handler']], filename='io_Brefs.png')
        # objgraph.show_backrefs([channels[0]], filename='chan_Brefs.png')
        QtGui.QApplication.instance().exec_()  # start Qt stuff

        # main window exit returns control to here
        # set termination flags
        config['handler'].do_polling = False
        config['handler'].kill_thread = True
        # clean up
        while config['poller'].isAlive() or config['handler'].ser.is_open:
            sleep(0.1)
        for thread in config['handler'].dsp_threads:
            while thread.isAlive():
                sleep(0.1)
        print 'Done.'
        # sys.exit(c.app.exec_())


if __name__ == '__main__':
    _main()
