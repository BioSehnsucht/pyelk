from collections import namedtuple
from collections import deque
import logging
import time
import traceback

_LOGGER = logging.getLogger(__name__)


class Event(object):
    EVENT_INSTALLER_CONNECT = 'RP' # ELKRP Connected
    EVENT_INSTALLER_EXIT = 'IE' # Installer Program Mode Exited

    EVENT_TROUBLE_STATUS = 'ss' # Request System Trouble Status
    EVENT_TROUBLE_STATUS_REPLY = 'SS' # Reply System Trouble Status

    EVENT_DISARM = 'a0' # Disarm
    EVENT_ARM_AWAY = 'a1' # Arm to Away
    EVENT_ARM_STAY = 'a2' # Arm to Stay (Home)
    EVENT_ARM_STAY_INSTANT = 'a3' # Arm to Stay Instant
    EVENT_ARM_NIGHT = 'a4' # Arm to Night
    EVENT_ARM_NIGHT_INSTANT = 'a5' # Arm to Night Instant
    EVENT_ARM_VACATION = 'a6' # Arm to Vacation
    EVENT_ARM_NEXT_AWAY = 'a7' # Arm, Step to Next Away mode
    EVENT_ARM_NEXT_STAY = 'a8' # Arm, Step to Next Stay mode
    EVENT_ARM_FORCE_AWAY = 'a9' # Force Arm to Away Mode
    EVENT_ARM_FORCE_STAY = 'a:' # Force Arm to Stay Mode
    EVENT_ARMING_STATUS = 'as' # Arming Status Request
    EVENT_ARMING_STATUS_REPORT = 'AS' # Reply Arming Status Report Data
    EVENT_ALARM_ZONE = 'az' # Alarm By Zone Request
    EVENT_ALARM_ZONE_REPORT = 'AZ' # Reply Alarm By zone Report Data
    EVENT_ALARM_MEMORY = 'AM' # Alarm Memory Update

    EVENT_ENTRY_EXIT_TIMER = 'EE' # Entry / Exit Timer Data

    EVENT_USER_CODE_ENTERED = 'IC' # Send Valid User Number And Invalid
                                       # User Code

    EVENT_KEYPAD_AREA = 'ka' # Request Keypad Area Assignments
    EVENT_KEYPAD_AREA_REPLY = 'KA' # Reply With Keypad Areas
    EVENT_KEYPAD_STATUS = 'kc' # Request Keypad Function Key Illumination
    EVENT_KEYPAD_STATUS_REPORT = 'KC' # Keypad KeyChange Update
                                   # Status
    EVENT_KEYPAD_PRESS = 'kf' # Request Keypad Function Key Press
    EVENT_KEYPAD_PRESS_REPLY = 'KF' # Reply Keypad Function Key Press
    EVENT_KEYPAD_TEXT = 'dm' # Display Text on LCD Screen

    EVENT_TEMP_ALL = 'lw' # Request Temperature Data (All Zones / Keypads)
    EVENT_TEMP_ALL_REPLY = 'LW' # Reply Temperature Data (All)
    EVENT_TEMP_REQUEST = 'st' # Request Temperature format
    EVENT_TEMP_REQUEST_REPLY = 'ST' # Reply With Requested Temperature

    EVENT_THERMOSTAT_DATA_REQUEST = 'tr' # Request Thermostat Data
    EVENT_THERMOSTAT_DATA_REPLY = 'TR' # Reply Thermostat Data
    EVENT_THERMOSTAT_SET = 'ts' # Set Thermostat Data

    EVENT_SPEAK_WORD = 'sw' # Speak Word at Voice/Siren Output
    EVENT_SPEAK_PHRASE = 'sp' # Speak Phrase at Voice/Siren Output

    EVENT_TASK_ACTIVATE = 'tn' # Task Activation
    EVENT_TASK_UPDATE = 'TC' # Tasks Change Update

    EVENT_VERSION = 'vn' # Request M1 Version Number
    EVENT_VERSION_REPLY = 'VN' # Request M1 Version Reply

    EVENT_OUTPUT_UPDATE = 'CC' # Output Change Update
    EVENT_OUTPUT_OFF = 'cf' # Control Output Off
    EVENT_OUTPUT_ON = 'cn' # Control Output On
    EVENT_OUTPUT_STATUS = 'cs' # Control Output Status Request
    EVENT_OUTPUT_STATUS_REPORT = 'CS' # Control Output Status Report
    EVENT_OUTPUT_TOGGLE = 'ct' # Control Output Toggle

    EVENT_ZONE_UPDATE = 'ZC' # Zone Change Update
    EVENT_ZONE_BYPASS = 'zb' # Zone Bypass Request
    EVENT_ZONE_BYPASS_REPLY = 'ZB' # Reply With Bypassed Zone State
    EVENT_ZONE_PARTITION = 'zp' # Zone Partition Request
    EVENT_ZONE_PARTITION_REPORT = 'ZP' # Zone Partition Report
    EVENT_ZONE_STATUS = 'zs' # Zone Status Request
    EVENT_ZONE_STATUS_REPORT = 'ZS' # Zone Status Report
    EVENT_ZONE_DEFINITION = 'zd' # Request Zone Definition
    EVENT_ZONE_DEFINITION_REPLY = 'ZD' # Reply Zone Definition Data
    EVENT_ZONE_TRIGGER = 'zt' # Zone Trigger
    EVENT_ZONE_VOLTAGE = 'zv' # Request Zone Voltage
    EVENT_ZONE_VOLTAGE_REPLY = 'ZV' # Reply Zone Analog Voltage Data

    EVENT_PLC_CONTROL = 'pc' # Control any PLC device
    EVENT_PLC_CHANGE_UPDATE = 'PC' # PLC Change Update
    EVENT_PLC_TURN_OFF = 'pf' # Turn OFF PLC Device
    EVENT_PLC_TURN_ON = 'pn' # Turn ON PLC Device
    EVENT_PLC_STATUS_REQUEST = 'ps' # Request PLC Status
    EVENT_PLC_STATUS_REPLY = 'PS' # Returned PLC Status
    EVENT_PLC_TOGGLE = 'pt' # Toggle PLC Device

    EVENT_VALUE_READ = 'cr' # Read Custom Value
    EVENT_VALUE_READ_ALL = 'cp' # Read ALL Custom Values
    EVENT_VALUE_READ_REPLY = 'CR' # Reply With Custom Value
    EVENT_VALUE_READ_ALL_REPLY = 'CP' # Reply With ALL Custom Values
    EVENT_VALUE_WRITE = 'cw' # Write Custom Value

    EVENT_COUNTER_READ = 'cv' # Read Counter Value
    EVENT_COUNTER_WRITE = 'cx' # Write Counter Value
    EVENT_COUNTER_REPLY = 'CV' # Reply With Counter Value Format

    EVENT_DESCRIPTION = 'sd' # Request ASCII String Text Descriptions
    EVENT_DESCRIPTION_REPLY = 'SD' # Reply with ASCII String Text
                                       # Description
    EVENT_ETHERNET_TEST = 'XK' # Elk to M1XEP test ping / time heartbeat

    DESCRIPTION_ZONE_NAME = 0
    DESCRIPTION_AREA_NAME = 1
    DESCRIPTION_USER_NAME = 2
    DESCRIPTION_KEYPAD_NAME = 3
    DESCRIPTION_OUTPUT_NAME = 4
    DESCRIPTION_TASK_NAME = 5
    DESCRIPTION_TELEPHONE_NAME = 6
    DESCRIPTION_LIGHT_NAME = 7
    DESCRIPTION_ALARM_DURATION_NAME = 8
    DESCRIPTION_CUSTOM_SETTING = 9
    DESCRIPTION_COUNTER_NAME = 10
    DESCRIPTION_THERMOSTAT_NAME = 11
    DESCRIPTION_FUNCTION_KEY_1_NAME = 12
    DESCRIPTION_FUNCTION_KEY_2_NAME = 13
    DESCRIPTION_FUNCTION_KEY_3_NAME = 14
    DESCRIPTION_FUNCTION_KEY_4_NAME = 15
    DESCRIPTION_FUNCTION_KEY_5_NAME = 16
    DESCRIPTION_FUNCTION_KEY_6_NAME = 17

    elk_events_map = {
        'RP' : EVENT_INSTALLER_CONNECT,
        'IE' : EVENT_INSTALLER_EXIT,
        'ss' : EVENT_TROUBLE_STATUS,
        'SS' : EVENT_TROUBLE_STATUS_REPLY,
        'a0' : EVENT_DISARM,
        'a1' : EVENT_ARM_AWAY,
        'a2' : EVENT_ARM_STAY,
        'a3' : EVENT_ARM_STAY_INSTANT,
        'a4' : EVENT_ARM_NIGHT,
        'a5' : EVENT_ARM_NIGHT_INSTANT,
        'a6' : EVENT_ARM_VACATION,
        'a7' : EVENT_ARM_NEXT_AWAY,
        'a8' : EVENT_ARM_NEXT_STAY,
        'a9' : EVENT_ARM_FORCE_AWAY,
        'a:' : EVENT_ARM_FORCE_STAY,
        'as' : EVENT_ARMING_STATUS,
        'AS' : EVENT_ARMING_STATUS_REPORT,
        'az' : EVENT_ALARM_ZONE,
        'AZ' : EVENT_ALARM_ZONE_REPORT,
        'AM' : EVENT_ALARM_MEMORY,
        'EE' : EVENT_ENTRY_EXIT_TIMER,
        'IC' : EVENT_USER_CODE_ENTERED,
        'ka' : EVENT_KEYPAD_AREA,
        'KA' : EVENT_KEYPAD_AREA_REPLY,
        'kc' : EVENT_KEYPAD_STATUS,
        'KC' : EVENT_KEYPAD_STATUS_REPORT,
        'kf' : EVENT_KEYPAD_PRESS,
        'KF' : EVENT_KEYPAD_PRESS_REPLY,
        'dm' : EVENT_KEYPAD_TEXT,
        'lw' : EVENT_TEMP_ALL,
        'LW' : EVENT_TEMP_ALL_REPLY,
        'st' : EVENT_TEMP_REQUEST,
        'ST' : EVENT_TEMP_REQUEST_REPLY,
        'sw' : EVENT_SPEAK_WORD,
        'sp' : EVENT_SPEAK_PHRASE,
        'tn' : EVENT_TASK_ACTIVATE,
        'TC' : EVENT_TASK_UPDATE,
        'vn' : EVENT_VERSION,
        'VN' : EVENT_VERSION_REPLY,
        'CC' : EVENT_OUTPUT_UPDATE,
        'cf' : EVENT_OUTPUT_OFF,
        'cn' : EVENT_OUTPUT_ON,
        'cs' : EVENT_OUTPUT_STATUS,
        'CS' : EVENT_OUTPUT_STATUS_REPORT,
        'ct' : EVENT_OUTPUT_TOGGLE,
        'ZC' : EVENT_ZONE_UPDATE,
        'zb' : EVENT_ZONE_BYPASS,
        'ZB' : EVENT_ZONE_BYPASS_REPLY,
        'zp' : EVENT_ZONE_PARTITION,
        'ZP' : EVENT_ZONE_PARTITION_REPORT,
        'zs' : EVENT_ZONE_STATUS,
        'ZS' : EVENT_ZONE_STATUS_REPORT,
        'zd' : EVENT_ZONE_DEFINITION,
        'ZD' : EVENT_ZONE_DEFINITION_REPLY,
        'zt' : EVENT_ZONE_TRIGGER,
        'zv' : EVENT_ZONE_VOLTAGE,
        'ZV' : EVENT_ZONE_VOLTAGE_REPLY,
        'cr' : EVENT_VALUE_READ,
        'cp' : EVENT_VALUE_READ_ALL,
        'CR' : EVENT_VALUE_READ_REPLY,
        'CP' : EVENT_VALUE_READ_ALL_REPLY,
        'cw' : EVENT_VALUE_WRITE,
        'cv' : EVENT_COUNTER_READ,
        'cx' : EVENT_COUNTER_WRITE,
        'CV' : EVENT_COUNTER_REPLY,
        'sd' : EVENT_DESCRIPTION,
        'SD' : EVENT_DESCRIPTION_REPLY
    }

    def __init__(self, pyelk = None):
        """Initialize Event object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        """
        self._len = 0
        self._type = ''
        self._data = []
        self._data_str = ''
        self._reserved = '00'
        self._checksum = ''
        self._time = time.time()
        self._pyelk = pyelk

    def age(self):
        """Age of the event (time since event was received)."""
        return time.time() - self._time

    def dump(self):
        """Dump debugging data, to be removed."""
        _LOGGER.debug('Event Len: ' + str(repr(self._len)))
        _LOGGER.debug('Event Type: ' + str(repr(self._type)))
        _LOGGER.debug('Event Data: ' + str(repr(self._data)))
        _LOGGER.debug('Event Data Str: ' + repr(self._data))
        _LOGGER.debug('Event Checksum: ' + str(repr(self._checksum)))
        _LOGGER.debug('Event Computed Checksum: ' + str(self.checksum_generate()))

    def parse(self, data):
        """Parse event packet."""
        _LOGGER.debug('Parsing: {}\n'.format(repr(data)))
        self._len = data[:2]
        self._type = data[2:4]
        if (len(data) > 8):
            self._data_str = data[4:-4]
            self._data = list(self._data_str)
        else:
            self._data_str = ''
            self._data = []
        self._reserved = data[-4:-2]
        self._checksum = data[-2:]

    def to_string(self):
        """Convert event data to string to be sent on the wire."""
        event_str = ''
        if ((self._data_str == '') and (len(self._data) > 0)):
            self._data_str = ''.join(self._data)
        event_str += self._type
        event_str += self._data_str
        event_str += self._reserved
        self._len = format(len(event_str) + 2, '02x').upper()
        self._checksum = self.checksum_generate(self._len + event_str)
        return self._len + event_str + self._checksum

    def checksum_generate(self, data = False):
        """Generate checksum for event.

        data: If set, is used instead of the data in the event object.
        """
        if (data == False):
            data = self._len + self._type + self._data_str + self._reserved
        CC = 0
        for c in data:
            CC += ord(c)
        CC = CC % 256
        CC = CC ^ 255
        CC += 1
        return format(CC, '02x').upper()

    def checksum_check(self):
        """Check if calculated checksum matches expected."""
        calculated = self.checksum_generate()
        if (calculated == self._checksum):
            return True
        else:
            return False

    def data_dehex(self, fake = False):
        """Convert ASCII hex data into integer data.

        fake: Set if not really ASCII hex, but instead is using all
        values from '0' onwards as offset by ord '0' from 0 (i.e. the
        value ':' is valid, and transates to 10, ';' is 11 ... 'A' is
        17, ...).
        """
        data = []
        for i in range(0,len(self._data)):
            data.append(ord(self._data[i]) - ord('0'))
            if (not fake) and (data[i] > 9):
                data[i] = data[i] - 7
        return data

    def data_str_dehex(self, fake = False):
        """Convert ASCII hex data into string data.

        fake: Set if not really ASCII hex, but instead is using all
        values from '0' onwards as offset by ord '0' from 0 (i.e. the
        value ':' is valid, and transates to 10, ';' is 11 ... 'A' is
        17, ...).
        """
        data = []
        for i in range(0,len(self._data)):
            data.append(str(ord(self._data[i]) - ord('0')))
            if (not fake) and (ord(data[i]) > 9):
                data[i] = str(ord(data[i]) - 7)
        return ''.join(data)
