from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class X10(Node):
    X10_ALL_UNITS_OFF = 1 # in a House code
    X10_ALL_LIGHTS_ON = 2 # in a House code
    X10_UNIT_ON = 3
    X10_UNIT_OFF = 4
    X10_DIM = 5 # Extended value holds number of dims
    X10_BRIGHT = 6 # Extended value holds number of brights
    X10_ALL_LIGHTS_OFF = 7 # in a House code
    X10_EXTENDED_CODE = 8
    X10_PRESET_DIM = 9 # Extended value hold level 0 to 99%
    X10_EXTENDED_DATA = 10
    X10_STATUS_REQ = 11
    X10_HAIL_REQUEST = 12
    X10_HAIL_ACK = 13 # Not used by Elk protocol
    X10_STATUS_ON = 14 # Not used by Elk protocol
    X10_STATUS_OFF = 15 # Not used by Elk protocol

    HOUSE_A = 1
    HOUSE_B = 2
    HOUSE_C = 3
    HOUSE_D = 4
    HOUSE_E = 5
    HOUSE_F = 6
    HOUSE_G = 7
    HOUSE_H = 8
    HOUSE_I = 9
    HOUSE_J = 10
    HOUSE_K = 11
    HOUSE_L = 12
    HOUSE_M = 13
    HOUSE_N = 14
    HOUSE_O = 15
    HOUSE_P = 16

    HOUSE_STR = {
        HOUSE_A : 'A',
        HOUSE_B : 'B',
        HOUSE_C : 'C',
        HOUSE_D : 'D',
        HOUSE_E : 'E',
        HOUSE_F : 'F',
        HOUSE_G : 'G',
        HOUSE_H : 'H',
        HOUSE_I : 'I',
        HOUSE_J : 'J',
        HOUSE_K : 'K',
        HOUSE_L : 'L',
        HOUSE_M : 'M',
        HOUSE_N : 'N',
        HOUSE_O : 'O',
        HOUSE_P : 'P'
        }

    STATUS_OFF = 0
    STATUS_ON = 1
    STATUS_DIMMED = 2

    STATUS_STR = {
        STATUS_OFF : 'Off',
        STATUS_ON : 'On',
        STATUS_DIMMED : 'Dimmed'
    }

    def __init__(self, pyelk = None, number = None):
        """Initializes X10 object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super(X10, self).__init__(pyelk, number)
        # Initialize PLC specific things
        self._house = X10.HOUSE_A
        self._level = 0

    def description(self):
        """X10 description, as text string (auto-generated if not set)."""
        if (self._description == '') or (self._description == None):
            self._enabled = False
        else:
            self._enabled = True
        return super(X10, self).description('Light ')

    def set_level(self, level):
        """Set brightness level of device.

        level: Brightness level, 0-100% as int (0 to 100)
        """
        if level < 2:
            self.turn_off()
        elif level > 99:
            self.turn_on()
        else:
            self.control(X10.X10_PRESET_DIM, level)

    def control(self, function, extended = 0, duration = 0):
        """Control X10 device.

        function: See X10_* constants
        extended: Brightness preset for X10_PRESET_DIM, or number of dim/bright for X10_DIM / X10_BRIGHT
        duration: Duration in seconds for output to turn on, 0 to 9999 decimal

        Event data format: HUUFFEETTTT
        H: House code 'A' to 'P'
        UU: Unit code '01' to '16'
        FF: Function code '01' to '16'
        EE: Extended code '00' to '99'
        TTTT: On time in seconds, 0000 to 9999
        """
        event = Event()
        event._type = Event.EVENT_PLC_CONTROL
        if duration < 0:
            duration = 0
        elif duration > 9999:
            duration = 9999
        event._data_str = X10.HOUSE_STR[self._house] \
            + format(self._number,'02') + format(function,'02') \
            + format(extended,'02') + format(duration,'04')
        self._pyelk.elk_event_send(event)

    def turn_on(self):
        """Turn on X10 device.

        Event data format: HUU
        H: House code 'A' to 'P'
        UU: Unit code '01' to '16'
        """
        event = Event()
        event._type = Event.EVENT_PLC_TURN_ON
        event._data_str = X10.HOUSE_STR[self._house] \
            + format(self._number,'02')
        self._pyelk.elk_event_send(event)

    def turn_off(self):
        """Turn off X10 device.

        Event data format: HUU
        H: House code 'A' to 'P'
        UU: Unit code '01' to '16'
        """
        event = Event()
        event._type = Event.EVENT_PLC_TURN_OFF
        event._data_str = X10.HOUSE_STR[self._house] \
            + format(self._number,'02')
        self._pyelk.elk_event_send(event)

    def toggle(self):
        """Toggle X10 device.

        Event data format: HUU
        H: House code 'A' to 'P'
        UU: Unit code '01' to '16'
        """
        event = Event()
        event._type = Event.EVENT_PLC_TOGGLE
        event._data_str = X10.HOUSE_STR[self._house] \
            + format(self._number,'02')
        self._pyelk.elk_event_send(event)

    def _state_from_int(self, state):
        if state == 0:
            self._status = X10.STATUS_OFF
            self._level = 0
        elif state == 1:
            self._status = X10.STATUS_ON
            self._level = 100
        else:
            self._status = X10.STATUS_DIMMED
            self._level = state

    def unpack_event_plc_change_update(self, event):
        """Unpack EVENT_PLC_CHANGE_UPDATE.

        Event data format: HUULL
        H: House code 'A' to 'P'
        UU: Unit code '01' to '16', '00' for All commands
        LL: Level / scene / state Status, 0 = OFF, 1 = ON, 2-99 = light%
        """
        state = int(event._data_str[3:5])
        self._state_from_int(state)
        self._updated_at = event._time
        self._callback()

    def unpack_event_plc_status_reply(self, event):
        """Unpack EVENT_PLC_STATUS_REPLY.

        Event data format: BD[64]
        B: Bank, 0=A1 to D16, 1=E1 to H16, 2=I1 to L16, 3=M1 to P16
        D[64]: 64 byte array ASCII encoded (D - 48 = 0); 0 = OFF, 1 = ON, 2-99 = light%
        """
        offset = (((self._house-1) * 16) + (self._number - 1)) % 64
        state = event.data_dehex(True)[1+offset]
        self._state_from_int(state)
        self._updated_at = event._time
        self._callback()
