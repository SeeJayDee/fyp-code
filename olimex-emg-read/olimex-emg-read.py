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

from pyqtgraph.Qt import QtGui, QtCore
import sys
import glob
import serial
import argparse
import datetime
from threading import Thread
from time import sleep
import classes as c

config = {'sampfreq' : 512,
          'title' : 'EMG Grapher',
          'width' : 1280,
          'height' : 800}

def serial_ports():
    """ Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform.')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


def record_data(ser):
    """ Read data from opened serial port ser and outputs to a file whose name
        is the current time.
        Adds the first line as column headings
    """
    filename = datetime.datetime.now().strftime("data_%Y-%m-%d_%H%M-%S") + ".csv"
    with open(filename, 'w') as output:
        samples = 0
        h = 'fc' # header value --- 0xFC
        h1 = ''
        h2 = ''
        output.write("OCRval,count,Ch0,Ch1,Ch2,Ch3\n")
        ser.reset_input_buffer()

        while ser.is_open and record_switch:
            if ser.in_waiting:
                h2 = ser.read().encode('hex')
                if (h2 == h) and (h1 == h):
                    h1 = ''
                    raw_data = ser.read(10)
                    output_line = "{},{},{},{},{},{}\n".format(ord(raw_data[0]), ord(raw_data[1]),
                                                               (ord(raw_data[2])<<8) + ord(raw_data[3]),
                                                               (ord(raw_data[4])<<8) + ord(raw_data[5]),
                                                               (ord(raw_data[6])<<8) + ord(raw_data[7]),
                                                               (ord(raw_data[8])<<8) + ord(raw_data[9]))
                    output.write(output_line)
                    samples += 1
                else:
                    h1 = h2

        print "Recorded {} samples to {}".format(samples, filename)

    return


# global (?) code here
#TODO: make it check the given serial port against the list of attached ports,
# and tell the user if it doesn't exist. If there's a problem with the 'port'
# arg, it should print the list of serial ports.
# It should also reject any baud rates outside the allowed values.
record_switch = False
parser = argparse.ArgumentParser()
parser.add_argument("port", help="the name of the serial port, ie \'COM3\' or \'/dev/ttyS0\'")
parser.add_argument("-b", "--baudrate",
                    help="the serial baud rate, ie 19200, 57600, 115200",
                    type=int, default=115200)


if __name__ == '__main__':
    if False:
        args = parser.parse_args()
        if args.port in serial_ports():
            arduino = serial.Serial()
            arduino.port = args.port
            arduino.baudrate = args.baudrate
            try:
                arduino.open()
                print 'connect success!'
            except (OSError, serial.SerialException):
                print 'Error opening serial port: ' + args.port
                exit(2)
            else:
                while True:
                    record_switch = True
                    rec_thread = Thread(target = record_data, args=(arduino, ))
                    rec_thread.start()
                    raw_input("Recording. Press enter to stop...")
                    record_switch = False
                    while rec_thread.isAlive():
                        sleep(0.1)

                    run = raw_input("\nRecord another sample? [y/N]: ")
                    if not run.lower().lstrip().startswith('y'):
                        break


        if arduino.is_open:
            arduino.close()
        exit(0)
    else:
        window = c.DisplayWindow(config)
        QtGui.QApplication.instance().exec_()
