from collections import namedtuple
from collections import deque
import logging
import serial
import serial.threaded
import time
import traceback

_LOGGER = logging.getLogger(__name__)


class Event(object):
    ELK_EVENT_INSTALLER_CONNECT = 'RP' # ELKRP Connected
    ELK_EVENT_INSTALLER_EXIT = 'IE' # Installer Program Mode Exited

    ELK_EVENT_TROUBLE_STATUS = 'ss' # Request System Trouble Status
    ELK_EVENT_TROUBLE_STATUS_REPLY = 'SS' # Reply System Trouble Status

    ELK_EVENT_DISARM = 'a0' # Disarm
    ELK_EVENT_ARM_AWAY = 'a1' # Arm to Away
    ELK_EVENT_ARM_STAY = 'a2' # Arm to Stay (Home)
    ELK_EVENT_ARM_STAY_INSTANT = 'a3' # Arm to Stay Instant
    ELK_EVENT_ARM_NIGHT = 'a4' # Arm to Night
    ELK_EVENT_ARM_NIGHT_INSTANT = 'a5' # Arm to Night Instant
    ELK_EVENT_ARM_VACATION = 'a6' # Arm to Vacation
    ELK_EVENT_ARM_NEXT_AWAY = 'a7' # Arm, Step to Next Away mode
    ELK_EVENT_ARM_NEXT_STAY = 'a8' # Arm, Step to Next Stay mode
    ELK_EVENT_ARM_FORCE_AWAY = 'a9' # Force Arm to Away Mode
    ELK_EVENT_ARM_FORCE_STAY = 'a:' # Force Arm to Stay Mode
    ELK_EVENT_ARMING_STATUS = 'as' # Arming Status Request
    ELK_EVENT_ARMING_STATUS_REPORT = 'AS' # Reply Arming Status Report Data
    ELK_EVENT_ALARM_ZONE = 'az' # Alarm By Zone Request
    ELK_EVENT_ALARM_ZONE_REPORT = 'AZ' # Reply Alarm By zone Report Data
    ELK_EVENT_ALARM_MEMORY = 'AM' # Alarm Memory Update

    ELK_EVENT_ENTRY_EXIT_TIMER = 'EE' # Entry / Exit Timer Data

    ELK_EVENT_USER_CODE_ENTERED = 'IC' # Send Valid User Number And Invalid
                                       # User Code

    ELK_EVENT_KEYPAD_AREA = 'ka' # Request Keypad Area Assignments
    ELK_EVENT_KEYPAD_AREA_REPLY = 'KA' # Reply With Keypad Areas
    ELK_EVENT_KEYPAD_STATUS = 'kc' # Request Keypad Function Key Illumination
    ELK_EVENT_KEYPAD_STATUS_REPORT = 'KC' # Keypad KeyChange Update
                                   # Status
    ELK_EVENT_KEYPAD_PRESS = 'kf' # Request Keypad Function Key Press
    ELK_EVENT_KEYPAD_PRESS_REPLY = 'KF' # Reply Keypad Function Key Press
    ELK_EVENT_KEYPAD_TEXT = 'dm' # Display Text on LCD Screen

    ELK_EVENT_TEMP_ALL = 'lw' # Request Temperature Data (All Zones / Keypads)
    ELK_EVENT_TEMP_ALL_REPLY = 'LW' # Reply Temperature Data (All)
    ELK_EVENT_TEMP_REQUEST = 'st' # Request Temperature format
    ELK_EVENT_TEMP_REQUEST_REPLY = 'ST' # Reply With Requested Temperature

    ELK_EVENT_SPEAK_WORD = 'sw' # Speak Word at Voice/Siren Output
    ELK_EVENT_SPEAK_PHRASE = 'sp' # Speak Phrase at Voice/Siren Output

    ELK_EVENT_TASK_ACTIVATE = 'tn' # Task Activation
    ELK_EVENT_TASK_UPDATE = 'TC' # Tasks Change Update

    ELK_EVENT_VERSION = 'vn' # Request M1 Version Number
    ELK_EVENT_VERSION_REPLY = 'VN' # Request M1 Version Reply

    ELK_EVENT_OUTPUT_UPDATE = 'CC' # Output Change Update
    ELK_EVENT_OUTPUT_OFF = 'cf' # Control Output Off
    ELK_EVENT_OUTPUT_ON = 'cn' # Control Output On
    ELK_EVENT_OUTPUT_STATUS = 'cs' # Control Output Status Request
    ELK_EVENT_OUTPUT_STATUS_REPORT = 'CS' # Control Output Status Report
    ELK_EVENT_OUTPUT_TOGGLE = 'ct' # Control Output Toggle

    ELK_EVENT_ZONE_UPDATE = 'ZC' # Zone Change Update
    ELK_EVENT_ZONE_BYPASS = 'zb' # Zone Bypass Request
    ELK_EVENT_ZONE_BYPASS_REPLY = 'ZB' # Reply With Bypassed Zone State
    ELK_EVENT_ZONE_PARTITION = 'zp' # Zone Partition Request
    ELK_EVENT_ZONE_PARTITION_REPORT = 'ZP' # Zone Partition Report
    ELK_EVENT_ZONE_STATUS = 'zs' # Zone Status Request
    ELK_EVENT_ZONE_STATUS_REPORT = 'ZS' # Zone Status Report
    ELK_EVENT_ZONE_DEFINITION = 'zd' # Request Zone Definition
    ELK_EVENT_ZONE_DEFINITION_REPLY = 'ZD' # Reply Zone Definition Data
    ELK_EVENT_ZONE_TRIGGER = 'zt' # Zone Trigger
    ELK_EVENT_ZONE_VOLTAGE = 'zv' # Request Zone Voltage
    ELK_EVENT_ZONE_VOLTAGE_REPLY = 'ZV' # Reply Zone Analog Voltage Data

    ELK_EVENT_VALUE_READ = 'cr' # Read Custom Value
    ELK_EVENT_VALUE_READ_ALL = 'cp' # Read ALL Custom Values
    ELK_EVENT_VALUE_READ_REPLY = 'CR' # Reply With Custom Value
    ELK_EVENT_VALUE_READ_ALL_REPLY = 'CP' # Reply With ALL Custom Values
    ELK_EVENT_VALUE_WRITE = 'cw' # Write Custom Value

    ELK_EVENT_COUNTER_READ = 'cv' # Read Counter Value
    ELK_EVENT_COUNTER_WRITE = 'cx' # Write Counter Value
    ELK_EVENT_COUNTER_REPLY = 'CV' # Reply With Counter Value Format

    ELK_EVENT_DESCRIPTION = 'sd' # Request ASCII String Text Descriptions
    ELK_EVENT_DESCRIPTION_REPLY = 'SD' # Reply with ASCII String Text
                                       # Description
    ELK_EVENT_ETHERNET_TEST = 'XK' # Elk to M1XEP test ping / time heartbeat

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

    elk_auto_map = [
            ELK_EVENT_INSTALLER_EXIT,
            ELK_EVENT_ALARM_MEMORY,
            ELK_EVENT_ENTRY_EXIT_TIMER,
            ELK_EVENT_USER_CODE_ENTERED,
            ELK_EVENT_TASK_UPDATE,
            ELK_EVENT_OUTPUT_UPDATE,
            ELK_EVENT_ZONE_UPDATE,
            ELK_EVENT_KEYPAD_STATUS_REPORT,
            ELK_EVENT_ETHERNET_TEST
            ]

    elk_events_map = {
        'RP' : ELK_EVENT_INSTALLER_CONNECT,
        'IE' : ELK_EVENT_INSTALLER_EXIT,
        'ss' : ELK_EVENT_TROUBLE_STATUS,
        'SS' : ELK_EVENT_TROUBLE_STATUS_REPLY,
        'a0' : ELK_EVENT_DISARM,
        'a1' : ELK_EVENT_ARM_AWAY,
        'a2' : ELK_EVENT_ARM_STAY,
        'a3' : ELK_EVENT_ARM_STAY_INSTANT,
        'a4' : ELK_EVENT_ARM_NIGHT,
        'a5' : ELK_EVENT_ARM_NIGHT_INSTANT,
        'a6' : ELK_EVENT_ARM_VACATION,
        'a7' : ELK_EVENT_ARM_NEXT_AWAY,
        'a8' : ELK_EVENT_ARM_NEXT_STAY,
        'a9' : ELK_EVENT_ARM_FORCE_AWAY,
        'a:' : ELK_EVENT_ARM_FORCE_STAY,
        'as' : ELK_EVENT_ARMING_STATUS,
        'AS' : ELK_EVENT_ARMING_STATUS_REPORT,
        'az' : ELK_EVENT_ALARM_ZONE,
        'AZ' : ELK_EVENT_ALARM_ZONE_REPORT,
        'AM' : ELK_EVENT_ALARM_MEMORY,
        'EE' : ELK_EVENT_ENTRY_EXIT_TIMER,
        'IC' : ELK_EVENT_USER_CODE_ENTERED,
        'ka' : ELK_EVENT_KEYPAD_AREA,
        'KA' : ELK_EVENT_KEYPAD_AREA_REPLY,
        'kc' : ELK_EVENT_KEYPAD_STATUS,
        'KC' : ELK_EVENT_KEYPAD_STATUS_REPORT,
        'kf' : ELK_EVENT_KEYPAD_PRESS,
        'KF' : ELK_EVENT_KEYPAD_PRESS_REPLY,
        'dm' : ELK_EVENT_KEYPAD_TEXT,
        'lw' : ELK_EVENT_TEMP_ALL,
        'LW' : ELK_EVENT_TEMP_ALL_REPLY,
        'st' : ELK_EVENT_TEMP_REQUEST,
        'ST' : ELK_EVENT_TEMP_REQUEST_REPLY,
        'sw' : ELK_EVENT_SPEAK_WORD,
        'sp' : ELK_EVENT_SPEAK_PHRASE,
        'tn' : ELK_EVENT_TASK_ACTIVATE,
        'TC' : ELK_EVENT_TASK_UPDATE,
        'vn' : ELK_EVENT_VERSION,
        'VN' : ELK_EVENT_VERSION_REPLY,
        'CC' : ELK_EVENT_OUTPUT_UPDATE,
        'cf' : ELK_EVENT_OUTPUT_OFF,
        'cn' : ELK_EVENT_OUTPUT_ON,
        'cs' : ELK_EVENT_OUTPUT_STATUS,
        'CS' : ELK_EVENT_OUTPUT_STATUS_REPORT,
        'ct' : ELK_EVENT_OUTPUT_TOGGLE,
        'ZC' : ELK_EVENT_ZONE_UPDATE,
        'zb' : ELK_EVENT_ZONE_BYPASS,
        'ZB' : ELK_EVENT_ZONE_BYPASS_REPLY,
        'zp' : ELK_EVENT_ZONE_PARTITION,
        'ZP' : ELK_EVENT_ZONE_PARTITION_REPORT,
        'zs' : ELK_EVENT_ZONE_STATUS,
        'ZS' : ELK_EVENT_ZONE_STATUS_REPORT,
        'zd' : ELK_EVENT_ZONE_DEFINITION,
        'ZD' : ELK_EVENT_ZONE_DEFINITION_REPLY,
        'zt' : ELK_EVENT_ZONE_TRIGGER,
        'zv' : ELK_EVENT_ZONE_VOLTAGE,
        'ZV' : ELK_EVENT_ZONE_VOLTAGE_REPLY,
        'cr' : ELK_EVENT_VALUE_READ,
        'cp' : ELK_EVENT_VALUE_READ_ALL,
        'CR' : ELK_EVENT_VALUE_READ_REPLY,
        'CP' : ELK_EVENT_VALUE_READ_ALL_REPLY,
        'cw' : ELK_EVENT_VALUE_WRITE,
        'cv' : ELK_EVENT_COUNTER_READ,
        'cx' : ELK_EVENT_COUNTER_WRITE,
        'CV' : ELK_EVENT_COUNTER_REPLY,
        'sd' : ELK_EVENT_DESCRIPTION,
        'SD' : ELK_EVENT_DESCRIPTION_REPLY
    }



    _len = 0
    _type = ''
    _data = []
    _data_str = ''
    _reserved = '00'
    _checksum = ''
    _time = 0

    def __init__(self, pyelk = None):
        _time = time.time()
        self._pyelk = pyelk

    def age(self):
        return time.time() - self._time

    def dump(self):
        _LOGGER.error('Event Len: ' + str(repr(self._len)))
        _LOGGER.error('Event Type: ' + str(repr(self._type)))
        _LOGGER.error('Event Data: ' + str(repr(self._data)))
        _LOGGER.error('Event Checksum: ' + str(repr(self._checksum)))
        _LOGGER.error('Event Computed Checksum: ' + str(self.checksum_generate()))

    def parse(self, data):
        _LOGGER.error('Parsing: {}\n'.format(repr(data)))
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
        event_str = ''
        if (self._data_str == ''):
            self._data_str = ''.join(self._data)
        event_str += self._type 
        event_str += self._data_str
        event_str += self._reserved
        self._len = format(len(event_str) + 2, '02x')
        self._checksum = self.checksum_generate(self._len + event_str)
        return self._len + event_str + self._checksum

    def checksum_generate(self, data = False):
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
        calculated = self.checksum_generate()
        if (calculated == self._checksum):
            return True
        else:
            return False

    def data_dehex(self, fake = False):
        data = [] 
        for i in range(0,len(self._data)):
            data.append(ord(self._data[i]) - ord('0'))
            if (not fake) and (data[i] > 9):
                data[i] = data[i] - 7
        return data

    def data_str_dehex(self, fake = False):
        data = []
        for i in range(0,len(self._data)):
            data.append(str(ord(self._data[i]) - ord('0')))
            if (not fake) and (ord(data[i]) > 9):
                data[i] = str(ord(data[i]) - 7)
        return ''.join(data)
    
