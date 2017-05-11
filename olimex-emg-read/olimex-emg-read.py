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

from collections import namedtuple
Config = namedtuple("Config", "baud num leng freq")

def load_config(filename):
    with open(filename, 'r') as configfile:
        lines = configfile.readlines()
        baud = int(lines[0].split('=')[1])
        num = int(lines[1].split('=')[1])
        leng = int(lines[2].split('=')[1]) + num + 1
        freq = int(lines[3].split('=')[1])
    return Config(baud, num, leng, freq)


if __name__ == '__main__':
    cfg = load_config("serial-config.txt")
    print cfg
    exit(0)
