# Desired function:
# The program should first attempt to load the config file.
# It should then open a new file ready for writing, named (emg-data-[[timestamp]])
# It should print 'NUMCHANNELS=X' and 'SAMPFREQ=Y' as the first two lines.
# Then the program needs to prompt the user for the serial port name (or take it
# as a command line arg).
# It should try to connect to the serial port, and immediately begin reading
# bytes and immediately discarding them (to keep buffer empty) while record-data
# is False.
# Then it should prompt the user to start recording. Once recording it will exit
# when a key is pressed.
# Once the user starts recording, record-data is set to True.
# While record-data is True, incoming bytes are read from the serial port. Once
# the header is received, the data that follows is converted to 10-bit and read
# into an array. Once the data from all channels is received, the contents of the
# array will be printed as comma-separated values on a new line of the output
# file, and the routine will revert to its initial state.

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
parser.add_argument("port", help="the name of the serial port, ie \'COM3\' or \'/dev/ttyS0\'")
parser.add_argument("-b", "--baudrate",
                    help="the serial baud rate, ie 19200, 57600, 115200",
                    type=int, default=115200)
parser.add_argument("-N", "--nowrite", action="store_true")
parser.add_argument("-R", "--raw_output", action="store_true")

# config = {'sampfreq': 256,
#           'datalen': 2048,
#           'mainsfreq': 50,
#           'notch_width': 1.0,
#           'filt_order': 3,
#           'raw_output': False,
#           'title': 'EMG Grapher',
#           'width': 1280,
#           'height': 800,
#           'plot_timer_ms': 50,
#           'plot_names': ['L_AS', 'L_AP', 'R_AS', 'R_AP'],
#           'indices': {'L_AS': 2, 'L_AP': 4, 'R_AS': 3, 'R_AP': 5}}
#
# cal = {'patterns': [['L_AS'], ['L_AP'], ['R_AS'], ['R_AP']],
#        'repeats': 3,
#        'intervals': [1., 2.]}

config = {'sampfreq': 256,
          'datalen': 4096,
          'mainsfreq': 50,
          'notch_width': 0.5,
          'filt_order': 3,
          'raw_output': False,
          'title': 'EMG Grapher',
          'width': 1280,
          'height': 800,
          'plot_timer_ms': 50,
          'plot_names': ['th_add', 'th_abd', 'fi_flx', 'fi_ext'],
          'indices': {'th_add': 2,
                      'th_abd': 4,
                      'fi_flx': 3,
                      'fi_ext': 5},
          'names': {'th_add': 'ADduct Thumb',
                    'th_abd': 'ABduct Thumb',
                    'fi_flx': 'Flex Fingers',
                    'fi_ext': 'Extend Fingers'},
          'keys': None}

prefixes = ['th', 'fi']
calcfg = {'repeats': 5,
    #    'intervals': [.1, .2]}
       'intervals': [1., 2.]}
config['calcfg'] = calcfg


def populate_patterns(prefix_list, cal_cfg):
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
        raise ImportError("Sorry: no implementation for your platform ('{}') available".format(os.name))

    result = []
    for (p, _, _) in sorted(comports()):
        result.append(p)
    return result


def _main():
    global config
    args = parser.parse_args()
    if args.port in serial_ports():
        if args.raw_output:
            config['raw_output'] = True
        channels = []
        config['cal'] = populate_patterns(prefixes, calcfg)
        config['win'] = c.DisplayWindow(config)
        for chname in config['plot_names']:
            channels.append(c.Channel(chname, config))
        channels = sorted(channels, key=lambda ch: ch.idx)
        config['handler'] = c.IO_handler(args.port, args.baudrate, channels, args.nowrite)
        config['poller'] = Thread(target=config['handler'].poll_serial, args=())
        config['poller'].start()
        QtGui.QApplication.instance().exec_()

        config['handler'].do_polling = False
        config['handler'].kill_thread = True
        while config['poller'].isAlive():
            sleep(0.1)
        for thread in config['handler'].dsp_threads:
            while thread.isAlive():
                sleep(0.1)
        print 'Done.'
        # sys.exit(c.app.exec_())


if __name__ == '__main__':
    _main()
