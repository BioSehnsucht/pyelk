from collections import namedtuple
from collections import deque
import logging
import serial
import serial.threaded
import time
import traceback

_LOGGER = logging.getLogger(__name__)

class Keypad(object):

    PRESSED_NONE = 0
    PRESSED_1 = 1
    PRESSED_2 = 2
    PRESSED_3 = 3
    PRESSED_4 = 4
    PRESSED_5 = 5
    PRESSED_6 = 6
    PRESSED_7 = 7
    PRESSED_8 = 8
    PRESSED_9 = 9
    PRESSED_0 = 10
    PRESSED_STAR = 11
    PRESSED_POUND = 12
    PRESSED_F1 = 13
    PRESSED_F2 = 14
    PRESSED_F3 = 15
    PRESSED_F4 = 16
    PRESSED_STAY = 17
    PRESSED_EXIT = 18
    PRESSED_CHIME = 19
    PRESSED_BYPASS = 20
    PRESSED_ELK = 21
    PRESSED_DOWN = 22
    PRESSED_UP = 23
    PRESSED_RIGHT = 24
    PRESSED_LEFT = 25
    PRESSED_F5 = 26
    PRESSED_F6 = 27
    PRESSED_DATAKEYMODE = 28

    PRESSED_STR = {
        PRESSED_NONE : 'None',
        PRESSED_1 : '1',
        PRESSED_2 : '2',
        PRESSED_3 : '3',
        PRESSED_4 : '4',
        PRESSED_5 : '5',
        PRESSED_6 : '6',
        PRESSED_7 : '7',
        PRESSED_8 : '8',
        PRESSED_9 : '9',
        PRESSED_0 : '0',
        PRESSED_STAR : '*',
        PRESSED_POUND : '#',
        PRESSED_F1 : 'F1',
        PRESSED_F2 : 'F2',
        PRESSED_F3 : 'F3',
        PRESSED_F4 : 'F4',
        PRESSED_STAY : 'Stay',
        PRESSED_EXIT : 'Exit',
        PRESSED_CHIME : 'Chime',
        PRESSED_BYPASS : 'Bypass',
        PRESSED_ELK : 'Elk',
        PRESSED_DOWN : 'Down',
        PRESSED_UP : 'Up',
        PRESSED_RIGHT : 'Right',
        PRESSED_LEFT : 'Left',
        PRESSED_F5 : 'F5',
        PRESSED_F6 : 'F6',
        PRESSED_DATAKEYMODE : 'Data Entered'
    }

    _area = 0
    _pressed = 0
    _illum = [0,0,0,0,0,0]
    _code_bypass = False
    _number = 0
    _temp = -460
    _updated_at = 0
    _update_callback = None

    def __init__(self, pyelk = None):
        self._pyelk = pyelk

    """
    PyElk.Event.EVENT_KEYPAD_AREA_REPLY
    """
    def unpack_event_keypad_area_reply(self, event):
        area = event.data_dehex(True)[self._number-1]
        if (area == self._area):
            return
        self._area = area
        self._pyelk.AREAS[self._area]._member_keypad[self._number] = True
        self._updated_at = event._time
        if self._update_callback:
            self._update_callback()


    """
    PyElk.Event.EVENT_KEYPAD_STATUS_REPORT
    """
    def unpack_event_keypad_status_report(self, event):
        key = int(event._data_str[:2])
        if (key == self._pressed):
            return
        self._pressed = key
        for i in range(0,6):
            self._illum[i] = event.data_dehex()[2+i]
        if (event._data[8] == '1'):
            self._code_bypass = True
        else:
            self._code_bypass = False
        # By area, not keypad
        for a in range(1,9):
            self._pyelk.AREAS[a]._chime_mode = event.data_dehex(True)[8+a-1]
        self._updated_at = event._time
        if self._update_callback:
            self._update_callback()

    """
    PyElk.Event.Event.EVENT_TEMP_REQUEST_REPLY
    """
    def unpack_event_temp_request_reply(self, event):
        data = int(event._data_str[4:6])
        data = data - 40
        self._temp = data
        self._updated_at = event._time
        if self._update_callback:
            self._update_callback()

    def age(self):
        return time.time() - self._updated_at

    def description(self):
        return 'Keypad ' + str(self._number)
