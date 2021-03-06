# === keylib.py ===
# * Function: contains keyboard event related functions.
# *
# * This is part of Christian D'Abrera's engineering final
# * year project titled "EMG Bio-feedback for rehabilitation".
# *
# * Christian D'Abrera
# * Curtin University 2017
# * christian.dabrera@student.curtin.edu.au
# * chrisdabrera@gmail.com

"""A library for the key-press related functions.

Originally named 'keytest.py'.
"""

from win32api import keybd_event
import time
import threading

loop = False;
pressed_keys = set()

Base = {
    '0': 48,    '1': 49,    '2': 50,    '3': 51,    '4': 52,
    '5': 53,    '6': 54,    '7': 55,    '8': 56,    '9': 57,
    'a': 65,    'b': 66,    'c': 67,    'd': 68,    'e': 69,
    'f': 70,    'g': 71,    'h': 72,    'i': 73,    'j': 74,
    'k': 75,    'l': 76,    'm': 77,    'n': 78,    'o': 79,
    'p': 80,    'q': 81,    'r': 82,    's': 83,    't': 84,
    'u': 85,    'v': 86,    'w': 87,    'x': 88,    'y': 89,
    'z': 90,    '.': 190,    '-': 189,    ',': 188,    '=': 187,
    '/': 191,    ';': 186,    '[': 219,    ']': 221,    '\\': 220,
    "'": 222,    'ALT': 18,    'TAB': 9,    'CAPSLOCK': 20,    'ENTER': 13,
    'BS': 8,    'CTRL': 17,    'ESC': 27,    ' ': 32,    'END': 35,
    'DOWN': 40,    'LEFT': 37,    'UP': 38,    'RIGHT': 39,    'SELECT': 41,
    'PRINTSCR': 44,    'INS': 45,    'DEL': 46,    'LWIN': 91,    'RWIN': 92,
    'LSHIFT': 160,    'SHIFT': 161,    'LCTRL': 162,    'RCTRL': 163,
    'VOLUP': 175,    'DOLDOWN': 174,    'NUMLOCK': 144,    'SCROLL': 145
    }

def KeyUp(Key, raw=False):
    if not raw:
        Key = Base[Key]
    if Key in pressed_keys:
        pressed_keys.remove(Key)
        keybd_event(Key, 0, 2, 0)


def KeyDown(Key, raw=False):
    if not raw:
        Key = Base[Key]
    if Key not in pressed_keys:
        pressed_keys.add(Key)
        keybd_event(Key, 0, 1, 0)


def loopKeys():
    """Test to see if win32api is legit."""
    while(loop):
        KeyDown('LEFT')
        time.sleep(1.5)
        KeyUp('LEFT')
        time.sleep(0.5)
        KeyDown('RIGHT')
        time.sleep(1.5)
        KeyUp('RIGHT')
        time.sleep(0.5)
        KeyDown(' ')
        time.sleep(0.25)
        KeyUp(' ')
        time.sleep(1.5)

if __name__ == '__main__':
    loop = True
    loop_t = threading.Thread(target=loopKeys, args=())
    loop_t.start()
    raw_input("Press [RETURN] to exit")
    loop = False
    while loop_t.isAlive():
        pass
