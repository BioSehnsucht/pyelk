from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class Thermostat(Node):
    MODE_OFF = 0
    MODE_HEAT = 1
    MODE_COOL = 2
    MODE_AUTO = 3
    MODE_HEAT_EMERGENCY = 4

    MODE_STR = {
        MODE_OFF : 'Off',
        MODE_HEAT : 'Heat',
        MODE_COOL : 'Cool',
        MODE_AUTO : 'Auto',
        MODE_HEAT_EMERGENCY : 'Emergency Heat'
        }

    HOLD_INACTIVE = 0
    HOLD_ACTIVE = 1

    HOLD_STR = {
        HOLD_INACTIVE : 'Inactive',
        HOLD_ACTIVE : 'Active'
        }

    FAN_AUTO = 0
    FAN_ON = 1

    FAN_STR = {
        FAN_AUTO : 'Auto',
        FAN_ON : 'On'
        }

    SET_MODE = 0
    SET_HOLD = 1
    SET_FAN = 2
    SET_GET_TEMP = 3
    SET_SETPOINT_COOL = 4
    SET_SETPOINT_HEAT = 5

    def __init__(self, pyelk=None, number=None):
        """Initializes Thermostat object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super().__init__(pyelk, number)
        # Initialize Thermostat specific things
        self._mode = None
        self._hold = None
        self._fan = None
        self._temp = -460
        self._setpoint_heat = None
        self._setpoint_cool = None
        self._humidity = None

    def description_pretty(self, prefix='Thermostat '):
        """Thermostat description, as text string (auto-generated if not set)."""
        return super().description_pretty(prefix)

    @property
    def mode(self):
        return self._mode

    @property
    def fan(self):
        return self._fan

    @property
    def temp(self):
        return self._temp

    @property
    def humidity(self):
        return self._humidity

    @property
    def setpoint_cool(self):
        return self._setpoint_cool

    @property
    def setpoint_heat(self):
        return self._setpoint_heat

    def mode_pretty(self):
        """Thermostat's current mode setting as text string."""
        if self._mode is not None:
            return self.MODE_STR[self._mode]
        return 'Unknown'

    def hold_pretty(self):
        """Thermostat's current hold setting as text string."""
        if self._hold is not None:
            return self.HOLD_STR[self._hold]
        return 'Unknown'

    def fan_pretty(self):
        """Thermostat's current fan setting as text string."""
        if self._fan is not None:
            return self.FAN_STR[self._fan]
        return 'Unknown'

    def _set_thermostat(self, setting, value):
        """Set the thermostat using our properties.

        Using EVENT_THERMOSTAT_SET.

        Event data format: NNVVE
        NN: Thermostat number (ASCII decimal 01 - 16)
        VV: Value to set (ASCII decimal 00 - 99 range)
        E: Element to set
        """

        event = Event()
        event.type = Event.EVENT_THERMOSTAT_SET
        event.data_str = format(self._number, '02') \
        + format(value, '02') + format(setting, '01')
        self._pyelk.elk_event_send(event)

    def set_mode(self, value):
        self._set_thermostat(self.SET_MODE, value)

    def set_hold(self, value):
        self._set_thermostat(self.SET_HOLD, value)

    def set_fan(self, value):
        self._set_thermostat(self.SET_FAN, value)

    def set_setpoint_cool(self, value):
        if value < 1:
            value = 1
        elif value > 99:
            value = 99
        self._set_thermostat(self.SET_SETPOINT_COOL, value)

    def set_setpoint_heat(self, value):
        if value < 1:
            value = 1
        elif value > 99:
            value = 99
        self._set_thermostat(self.SET_SETPOINT_HEAT, value)

    def request_temp(self):
        self._set_thermostat(self.SET_GET_TEMP, 0)

    def unpack_event_temp_request_reply(self, event):
        """Unpack EVENT_TEMP_REQUEST_REPLY.

        Event data format: GNNDDD
        G: Requested Group ('2')
        NN: Device number in group (2 decimal ASCII digits)
        DDD: Temperature in ASCII decimal (no offset)
        """
        data = int(event.data_str[3:6])
        data = data - 40
        self._temp = data
        self._updated_at = event.time
        self._callback()

    def unpack_event_thermostat_data_reply(self, event):
        """Unpack EVENT_THERMOSTAT_DATA_REPLY.

        Event data format: NNMHFTTHHSSUU
        NN: Thermostat number (ASCII decimal 01 - 16)
        M: Thermostat Mode
        H: Thermostat Hold (True if '1')
        F: Thermostat Fan Mode
        TT: Current Temperature (ASCII decimal, 00 is invalid)
        HH: Heat Set Point in Heat/Auto modes (ASCII decimal)
        SS: Cool Set Point in Cool/Auto modes (ASCII decimal)
        UU: Current Humidity % (ASCII decimal, 01 to 99)
        """
        self._mode = int(event.data_str[2:3])
        self._hold = int(event.data_str[3:4])
        self._fan = int(event.data_str[4:5])
        self._temp = int(event.data_str[5:7])
        self._setpoint_heat = int(event.data_str[7:9])
        self._setpoint_cool = int(event.data_str[9:11])
        self._humidity = int(event.data_str[11:13])
        if self._temp == 0:
            self._enabled = False
        self._updated_at = event.time
        self._callback()
