from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Node import Node

_LOGGER = logging.getLogger(__name__)

class Keypad(Node):

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

    def __init__(self, pyelk = None, number = None):
        """Initializes Keypad object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super(Keypad, self).__init__(pyelk, number)
        # Initialize Keypad specific things
        self._pressed = 0
        self._illum = [0,0,0,0,0,0]
        self._code_bypass = False
        self._temp = -460

    def description(self):
        """Keypad description, as text string (auto-generated if not set)."""
        return super(Keypad, self).description('Keypad ')

    def unpack_event_keypad_area_reply(self, event):
        """Unpack EVENT_KEYPAD_AREA_REPLY."""
        area = event.data_dehex(True)[self._number-1]
        self._area = area
        for a in range(1,9):
            self._pyelk.AREAS[a]._member_keypad[self._number] = False
        if self._area > 0:
            self._pyelk.AREAS[self._area]._member_keypad[self._number] = True

        self._updated_at = event._time
        self._callback()

    def unpack_event_keypad_status_report(self, event):
        """Unpack EVENT_KEYPAD_STATUS_REPORT."""
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
        # Chime is actually by area, not keypad, even though
        # it is returned from the keypad status report.
        for a in range(1,9):
            self._pyelk.AREAS[a]._chime_mode = event.data_dehex(True)[8+a-1]
        self._updated_at = event._time
        self._callback()

    def unpack_event_temp_request_reply(self, event):
        """Unpack EVENT_TEMP_REQUEST_REPLY."""
        data = int(event._data_str[3:6])
        data = data - 40
        self._temp = data
        self._updated_at = event._time
        self._callback()
