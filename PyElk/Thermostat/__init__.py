"""Elk Thermostat."""
from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Const import *
from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class Omni2Message():
    REQ_POLL_REGISTERS = 0
    REQ_SET_REGISTERS = 1
    REQ_POLL_GROUP_1 = 2
    REQ_POLL_GROUP_2 = 3
    REQ_POLL_GROUP_3 = 4

    RESP_ACK = 0
    RESP_NACK = 1
    RESP_DATA = 2 # Response to REQ_POLL_REGISTERS
    RESP_GROUP_1 = 3
    RESP_GROUP_2 = 4
    RESP_GROUP_3 = 5

    REG_SETUP_COMM_ADDRESS = 0
    REG_SETUP_COMM_BAUD = 1
    REG_SETUP_SYSTEM_TYPE = 2
    REG_SETUP_DISPLAY_OPTIONS = 3
    REG_SETUP_CALIBRATION_OFFSET = 4
    REG_SETUP_LOW_COOL = 5
    REG_SETUP_HIGH_HEAT = 6
    REG_SETUP_ENERGY_EFFICIENT_CONTROL = 7
    REG_SETUP_OMNI_VERSION = 8
    REG_SETUP_COOL_ANTICIPATOR = 9
    REG_SETUP_SECOND_STAGE_DIFF = 10
    REG_SETUP_COOLING_CYCLE_TIME = 11
    REG_SETUP_HEATING_CYCLE_TIME = 12
    REG_SETUP_THIRD_STAGE_DIFF = 13
    REG_SETUP_CLOCK_ADJUST = 14
    REG_SETUP_FILTER_DAYS_REMAIN = 15
    REG_SETUP_RUN_TIME_CURRENT_WEEK = 16
    REG_SETUP_RUN_TIME_LAST_WEEK = 17
    REG_SETUP_PROGRAM_MODE = 131 # 0:None, 1:Schedule, 2:Occupancy
    REG_SETUP_EXPANSION_BAUD = 132 # 0:300, 1:100, 42:1200, 54=2400, 126=9600
    REG_SETUP_DAYS_UNTIL_FILTER_REMINDER = 133
    REG_SETUP_HUMIDITY_SETPOINT = 134
    REG_SETUP_DEHUMIDIFY_SETPOINT = 135
    REG_SETUP_DEHUMIDIFIER_OUTPUT = 136 # 0:Not Used, 1:Standalone, 2:Variable
    REG_SETUP_HUMIDIFIER_OUTPUT = 137 # 0:Not used, 1:Standalone
    REG_SETUP_FAN_CYCLE_MINUTES = 138 # 0..19 min out of 20 to run in cycle
    REG_SETUP_BACKLIGHT_SETTING = 139 # 0:Off, 1:On, 2:Auto
    REG_SETUP_BACKLIGHT_COLOR = 140 # 0-100
    REG_SETUP_BACKLIGHT_INTENSITY = 141 # 0-10
    REG_SETUP_SELECTIVE_MESSAGE = 142
    REG_SETUP_MINIMUM_COOL_ON_TIME = 143 # 2-30
    REG_SETUP_MINIMUM_COOL_OFF_TIME = 144 # 2-30
    REG_SETUP_MINIMUM_HEAT_ON_TIME = 145 # 2-30
    REG_SETUP_MINIMUM_HEAT_OFF_TIME = 146 # 2-30
    REG_SETUP_SYSTEM_TYPE = 147 # 0:Heat Pump, 1:Conventional, 2:Duel Fuel
    REG_SETUP_END_OF_VACATION_DAY = 149
    REG_SETUP_END_OF_VACATION_HOUR = 150
    REG_SETUP_HOURS_USED_WEEK_0 = 151
    REG_SETUP_HOURS_USED_WEEK_1 = 152
    REG_SETUP_HOURS_USED_WEEK_2 = 153
    REG_SETUP_HOURS_USED_WEEK_3 = 154
    REG_SETUP_ENABLE_TEMP_SENSORS = 158
    REG_SETUP_COOL_STAGES = 159
    REG_SETUP_HEAT_STAGES = 160
    REG_SETUP_OCCUPANCY_MODE = 161 # 0:Day, 1:Night, 2:Away, 3:Vacation
    REG_SETUP_INDOOR_HUMIDITY = 162
    REG_SETUP_VACATION_SETPOINT_COOL = 163
    REG_SETUP_VACATION_SETPOINT_HEAT = 164

    REG_STATUS_OUTSIDE_HUMIDITY = 57
    REG_STATUS_CURRENT_DAY_OF_WEEK = 58
    REG_STATUS_COOL_SETPOINT = 59
    REG_STATUS_HEAT_SETPOINT = 60
    REG_STATUS_SYS_MODE = 61 # 0:Off, 1:Heat, 2:Cool, 3:Auto, 4: Em. Heat
    REG_STATUS_FAN_MODE = 62 # 0:Off, 1:On, 2:Cycle
    REG_STATUS_HOLD_MODE = 63 # 0:Off, 1:On, 2:Vacation
    REG_STATUS_TEMPERATURE = 64
    REG_STATUS_TIME_SECONDS = 65
    REG_STATUS_TIME_MINUTES = 66
    REG_STATUS_TIME_HOURS = 67
    REG_STATUS_OUTSIDE_TEMP = 68
    REG_STATUS_ENERGY_PRICE = 70 # 0:Low, 1:Mid, 2:High, 3:Critical
    REG_STATUS_CURRENT_MODE = 71 # 0:Off, 1:Heat, 2:Cold
    REG_STATUS_RELAYS = 72
    REG_STATUS_MODEL = 73
    REG_STATUS_CURRENT_ENERGY_COST = 74 # 0-254, 255=disabled

    REG_SENSORS_CURRENT_TEMP_3 = 200
    REG_SENSORS_CURRENT_TEMP_4 = 201

    REG_ENERGY_SETBACK_MEDIUM = 18
    REG_ENERGY_SETBACK_HIGH = 19
    REG_ENERGY_SETBACK_CRITICAL = 20
    REG_ENERGY_DISPLAY_PRICE_ENERGY_MEDIUM = 165
    REG_ENERGY_DISPLAY_PRICE_ENERGY_HIGH = 166
    REG_ENERGY_DISPLAY_PRICE_ENERGY_CRITICAL = 167
    REG_ENERGY_PROXIMITY_SENSITIVITY = 168 # 0-99
    REG_ENERGY_LEVEL_SET_BY_METER = 169
    REG_ENERGY_TOTAL_COST_UPPER_BYTE = 170
    REG_ENERGY_TOTAL_COST_LOWER_BYTE = 171

    # For the following REG_PROG_* :
    # Actual register is REG_PROG_[day] +
    #     REG_PROG_[morning|day|evening|night] +
    #     REG_PROG_[time|cool|heat]
    REG_PROG_MON = 21
    REG_PROG_TUE = 75
    REG_PROG_WED = 87
    REG_PROG_THU = 99
    REG_PROG_FRI = 111
    REG_PROG_SAT = 33
    REG_PROG_SUN = 45
    REG_PROG_TIME = 0
    REG_PROG_COOL = 1
    REG_PROG_HEAT = 2
    REG_PROG_MORNING = 0
    REG_PROG_DAY = 3
    REG_PROG_EVENING = 6
    REG_PROG_NIGHT = 9

    REG_PROG_OCCUPANCY_DAY_COOL = 123
    REG_PROG_OCCUPANCY_DAY_HEAT = 124
    REG_PROG_OCCUPANCY_NIGHT_COOL = 125
    REG_PROG_OCCUPANCY_NIGHT_HEAT = 126
    REG_PROG_OCCUPANCY_AWAY_COOL = 127
    REG_PROG_OCCUPANCY_AWAY_HEAT = 128
    REG_PROG_OCCUPANCY_VACATION_COOL = 129
    REG_PROG_OCCUPANCY_VACATION_HEAT = 130

    def __init__(self):
        """Initializes Omni2 Message object."""
        self._number = None
        self._length = None
        self._msg_type = None
        self._data = None
        self._checksum = None

    @property
    def number(self):
        return self._number

    @number.setter
    def number(self, value):
        self._number = value

    @property
    def length(self):
        return self._length

    @property
    def msg_type(self):
        return self._msg_type

    @msg_type.setter
    def msg_type(self, value):
        self._msg_type = value

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        self._data = value

    @property
    def checksum(self):
        return self._checksum

    def _calculate_checksum(self):
        checksum = 0
        checksum = checksum + self._number
        checksum = checksum + int(
            format(self._length, '1x') + format(self._msg_type, '1x'), 16)
        for dc in self._data:
            if isinstance(dc, str):
                dc = ord(dc)
            checksum = checksum + dc
        self._checksum = checksum
        return self._checksum

    def encode(self):
        message = ''
        number = format(self._number, '02x')
        len_type = format(self._length, '1x') + format(self._msg_type, '1x')
        data = ''
        for dc in self._data:
            if isinstance(dc, str):
                dc = ord(dc)
            data = data + format(dc, '02x')
        checksum = self._calculate_checksum()
        message = number + len_type + data + checksum
        return message

    def decode(self, message):
        self._number = int(message[0:2],16)
        self._length = int(message[2],16)
        self._msg_type = int(message[3],16)
        self._data = []
        if self._length > 0:
            data = message[4:4+length]
            for di in range(0,length):
                self._data.append(data[di*2:(di*2)+2])

class Thermostat(Node):
    """Represents a Thermostat in the Elk."""
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
        self._setpoint_heat = 0
        self._setpoint_cool = 0
        self._humidity = 0
        self._omni2 = None

    def description_pretty(self, prefix='Thermostat '):
        """Thermostat description, as text string (auto-generated if not set)."""
        return super().description_pretty(prefix)

    @property
    def mode(self):
        """Return the current mode of thermostat."""
        return self._mode

    @property
    def fan(self):
        """Return the current fan setting of thermostat."""
        return self._fan

    @property
    def temp(self):
        """Return the current temperature reported by thermostat."""
        return self._temp

    @property
    def humidity(self):
        """Return the current humidity reported by thermostat."""
        return self._humidity

    @property
    def setpoint_cool(self):
        """Return the current cooling setpoint."""
        return self._setpoint_cool

    @property
    def setpoint_heat(self):
        """Return the current heating setpoint."""
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
        """Set the thermostat operation mode."""
        self._set_thermostat(self.SET_MODE, value)

    def set_hold(self, value):
        """Set the thermostat hold setting."""
        self._set_thermostat(self.SET_HOLD, value)

    def set_fan(self, value):
        """Set the thermostat fan setting."""
        self._set_thermostat(self.SET_FAN, value)

    def set_setpoint_cool(self, value):
        """Set the thermostat cool setpoint."""
        if value < 1:
            value = 1
        elif value > 99:
            value = 99
        self._set_thermostat(self.SET_SETPOINT_COOL, value)

    def set_setpoint_heat(self, value):
        """Set the thermostat heat setpoint."""
        if value < 1:
            value = 1
        elif value > 99:
            value = 99
        self._set_thermostat(self.SET_SETPOINT_HEAT, value)

    def request_temp(self):
        """Request temperature update from thermostat."""
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
        temp = int(event.data_str[5:7])
        # Sometimes temp reports zero incorrectly, ignore it
        if temp > 0:
            self._temp = temp
        self._setpoint_heat = int(event.data_str[7:9])
        self._setpoint_cool = int(event.data_str[9:11])
        humidity = int(event.data_str[11:13])
        # Sometimes humitity reports zero incorrectly, ignore it
        if humidity > 0:
            self._humidity = humidity
        # Sometimes temp/humidity are reported as zero, even though
        # the thermostat is present and "working"
        # Only indicate not detected if setpoints are zero too
        if ((self._temp <= 0) and (self._setpoint_cool <= 0) and
            (self._setpoint_heat <= 0) and (self._humidity <= 0)):
            self._enabled = False
        else:
            self._enabled = True
        self._updated_at = event.time
        self._callback()

    def unpack_event_omnistat_data_reply(self, event):
        """Unpack EVENT_OMNISTAT_DATA_REPLY.

        Event data format: D[36]
        D[36]: Array of ASCII hex values representing 18 bytes of
               Omnistat 2 binary protocol
        """
        message = Omni2Message()
        message.decode(event.data)
        if message.number != self._number:
            return
        self._omni2 = True
        if message.msg_type == message.RESP_GROUP_1:
            temp_c = -40 + (0.5 * message.data[5])
            self._temp = round((temp_c * 1.8) + 32)
            return
        if message.msg_type == message.RESP_GROUP_2:
            self._humidity = message.data[0]
            return
        if message.msg_type == message.RESP_DATA:
            start_reg = message.data[0]
            for reg in range(0,len(message.data)-1):
                if (start_reg + reg) == message.REG_SETUP_INDOOR_HUMIDITY:
                    self._humidity = message.data[reg+1]
                if (start_reg + reg) == message.REG_STATUS_TEMPERATURE:
                    temp_c = -40 + (0.5 * message.data[reg+1])
                    self._temp = round((temp_c * 1.8) + 32)
            return
        return