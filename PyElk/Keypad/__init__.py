"""Elk Keypad."""
from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Const import *
from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class Keypad(Node):
    """Represents a Keypad in the Elk."""
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

    def __init__(self, pyelk=None, number=None):
        """Initializes Keypad object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super().__init__('Keypad', pyelk, number)
        # Initialize Keypad specific things
        self._pressed = 0
        self._illum = [0, 0, 0, 0, 0, 0]
        self._code_bypass = False
        self._temp = -460
        self._temp_enabled = False
        self._last_user_num = -1
        self._last_user_at = 0
        self._last_user_name = 'N/A'

    def state_save(self):
        """Returns a save state object for fast load functionality."""
        data = super().state_save()
        data['last_user_num'] = self._last_user_num
        data['last_user_at'] = self._last_user_at
        data['last_user_name'] = self._last_user_name
        data['temp_enabled'] = self._temp_enabled
        data['temp'] = self._temp
        return data

    def state_load(self, state):
        """Loads a save state object for fast load functionality."""
        super().state_load(state)
        for state_key in state:
            if state_key == 'last_user_num':
                self._last_user_num = state['last_user_num']
            elif state_key == 'last_user_at':
                self._last_user_at = state['last_user_at']
            elif state_key == 'last_user_at':
                self._last_user_name = state['last_user_name']
            elif state_key == 'temp_enabled':
                self._temp_enabled = state['temp_enabled']
            elif state_key == 'temp':
                self._temp = state['temp']
        if self._area is not None and self._area > 0:
            self._pyelk.AREAS[self._area_index].member_keypad[self._index] = True

    @property
    def temp(self):
        """Returns the current temperature."""
        return self._temp

    @property
    def temp_enabled(self):
        """Returns whether temperature readings are available / enabled."""
        return self._temp_enabled

    @property
    def last_user_code(self):
        """Returns last user code entered on keypad."""
        return self._last_user_num

    @property
    def last_user_at(self):
        """Returns last user code entered timestamp."""
        return self._last_user_at

    @property
    def last_user_name(self):
        """Returns name of the last used user code."""
        return self._last_user_name

    def description_pretty(self, prefix='Keypad '):
        """Keypad description, as text string (auto-generated if not set)."""
        return super().description_pretty(prefix)

    def unpack_event_keypad_area_reply(self, event):
        """Unpack EVENT_KEYPAD_AREA_REPLY.

        Event data format: D[16]
        D[16]: 16 byte ASCII character array of area assignments, where
        '0' is no area assigned, '1' is assigned to Area 1, etc
        """
        area = event.data_dehex(True)[self._index]
        self._area = area
        self._area_index = self._area - 1
        for node_index in range(0, AREA_MAX_COUNT):
            self._pyelk.AREAS[node_index].member_keypad[self._index] = False
        if self._area > 0:
            self._pyelk.AREAS[self._area_index].member_keypad[self._index] = True
        self._updated_at = event.time
        self._callback()
        self._pyelk.AREAS[self._area_index]._updated_at = event.time
        self._pyelk.AREAS[self._area_index]._callback()

    def unpack_event_keypad_status_report(self, event):
        """Unpack EVENT_KEYPAD_STATUS_REPORT.

        Event data format: NNDDLLLLLLCPPPPPPPP
        NN: Keypad number in ASCII decimal
        DD: Key number pressed (see PRESSED_* constants)
        L[6]: 6 byte ASCII character array indicating keypad function
        key illumination status (0 = off, 1 = on, 2 = blinking)
        C: If '1', code required to bypass
        P[8]: Beep and chime mode per Area (See Area constants)
        """
        keypad_number = int(event.data_str[0:2])
        key_pressed = int(event.data_str[2:4])
        if key_pressed != self._pressed:
            self._pressed = key_pressed
        for i in range(0, 6):
            self._illum[i] = event.data_dehex()[4+i]
        if event.data[10] == '1':
            self._code_bypass = True
        else:
            self._code_bypass = False
        # Chime is actually by area, not keypad, even though
        # it is returned from the keypad status report.
        for node_index in range(0, AREA_MAX_COUNT):
            self._pyelk.AREAS[node_index].chime_mode = event.data_dehex(True)[11+node_index]
        self._updated_at = event.time
        self._callback()

    def unpack_event_temp_request_reply(self, event):
        """Unpack EVENT_TEMP_REQUEST_REPLY.

        Event data format: GNNDDD
        G: Requested Group ('1')
        NN: Device number in group (2 decimal ASCII digits)
        DDD: Temperature in ASCII decimal (offset by -40 for true value)
        """
        data = int(event.data_str[3:6])
        data = data - 40
        self._temp = data
        if self._temp == -40:
            self._temp_enabled = False
        else:
            self._temp_enabled = True
        self._updated_at = event.time
        self._callback()

    def unpack_event_user_code_entered(self, event):
        """Unpack EVENT_USER_CODE_ENTERED.

        Event data format: DDDDDDDDDDDDUUUNN
        DDDDDDDDDDDD: 12 characters of ASCII Hex user code data,
        4 & 6 digits codes are left padded with zeros. Set to all
        zeros if code is valid
        UUU: 3 characters of ASCII decimal User Code Number 001 to 103,
        indicating which valid user code was entered
        NN: Keypad number that generated the code
        """
        # failed_code = event.data_str[0:12]
        user = int(event.data_str[12:15])
        user = user - 1
        # keypad_number = int(event.data_str[15:17])
        if user < 0:
            # Invalid code was entered
            self._last_user_name = 'Invalid'
        else:
            # Valid user code was entered
            self._last_user_name = self._pyelk.USERS[user].description
        self._last_user_num = user
        self._last_user_at = event.time
        if self._area > 0:
            self._pyelk.AREAS[self._area_index].last_user_num = user
            self._pyelk.AREAS[self._area_index].last_user_at = event.time
            self._pyelk.AREAS[self._area_index].last_user_name = self._last_user_name
            self._pyelk.AREAS[self._area_index].last_keypad_num = self._number
            self._pyelk.AREAS[self._area_index].last_keypad_name = self._description
            # Force area update to propogate the last user code / at update
            self._pyelk.AREAS[self._area_index].updated_at = event.time
            self._pyelk.AREAS[self._area_index].callback_trigger()
        self._updated_at = event.time
        self._callback()
