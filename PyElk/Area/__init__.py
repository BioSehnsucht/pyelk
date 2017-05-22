from collections import namedtuple
from collections import deque
import logging
import serial
import serial.threaded
import time
import traceback

_LOGGER = logging.getLogger(__name__)

class Area(object):
    STATUS_DISARMED = 0
    STATUS_ARMED_AWAY = 1
    STATUS_ARMED_STAY = 2
    STATUS_ARMED_STAY_INSTANT = 3
    STATUS_ARMED_NIGHT = 4
    STATUS_ARMED_NIGHT_INSTANT = 5
    STATUS_ARMED_VACATION = 6

    STATUS_STR = {
        STATUS_DISARMED : 'Disarmed',
        STATUS_ARMED_AWAY : 'Armed Away',
        STATUS_ARMED_STAY : 'Armed Stay',
        STATUS_ARMED_STAY_INSTANT : 'Armed Stay Instant',
        STATUS_ARMED_NIGHT : 'Armed to Night',
        STATUS_ARMED_NIGHT_INSTANT : 'Armed to Night Instant',
        STATUS_ARMED_VACATION : 'Armed to Vacation'
    }

    ARM_UP_NOT_READY = 0
    ARM_UP_READY = 1
    ARM_UP_READY_VIOLATED_BYPASS = 2
    ARM_UP_ARMED_EXIT_TIMER = 3
    ARM_UP_ARMED = 4
    ARM_UP_FORCE_ARMED_VIOLATED = 5
    ARM_UP_ARMED_BYPASS = 6

    ARM_UP_STR = {
        ARM_UP_NOT_READY : 'Not Ready To Arm',
        ARM_UP_READY : 'Ready To Arm',
        ARM_UP_READY_VIOLATED_BYPASS : 'Ready To Arm, but a zone is violated and can be Force Armed',
        ARM_UP_ARMED_EXIT_TIMER : 'Armed with Exit Timer working',
        ARM_UP_ARMED : 'Armed Fully',
        ARM_UP_FORCE_ARMED_VIOLATED : 'Force Armed with a force arm zone violated',
        ARM_UP_ARMED_BYPASS : 'Armed with a bypass'
    }

    ALARM_NONE = 0
    ALARM_ENTRANCE_DELAY = 1
    ALARM_ABORT_DELAY = 2
    ALARM_FULL_FIRE = 3
    ALARM_FULL_MEDICAL = 4
    ALARM_FULL_POLICE = 5
    ALARM_FULL_BURGLAR = 6
    ALARM_FULL_AUX_1 = 7
    ALARM_FULL_AUX_2 = 8
    ALARM_FULL_AUX_3 = 9
    ALARM_FULL_AUX_4 = 10
    ALARM_FULL_CARBON_MONOXIDE = 11
    ALARM_FULL_EMERGENCY = 12
    ALARM_FULL_FREEZE = 13
    ALARM_FULL_GAS = 14
    ALARM_FULL_HEAT = 15
    ALARM_FULL_WATER = 16
    ALARM_FULL_FIRE_SUPERVISORY = 17
    ALARM_FULL_FIRE_VERIFY = 18

    ALARM_STR = {
        ALARM_NONE : 'No Alarm Active',
        ALARM_ENTRANCE_DELAY : 'Entrance Delay is Active',
        ALARM_ABORT_DELAY : 'Alarm Abort Delay Active',
        ALARM_FULL_FIRE : 'Fire Alarm',
        ALARM_FULL_MEDICAL : 'Medical Alarm',
        ALARM_FULL_POLICE : 'Police Alarm',
        ALARM_FULL_BURGLAR : 'Burglar Alarm',
        ALARM_FULL_AUX_1 : 'Aux 1 Alarm',
        ALARM_FULL_AUX_2 : 'Aux 2 Alarm',
        ALARM_FULL_AUX_3 : 'Aux 3 Alarm',
        ALARM_FULL_AUX_4 : 'Aux 4 Alarm',
        ALARM_FULL_CARBON_MONOXIDE : 'Carbon Monoxide Alarm',
        ALARM_FULL_EMERGENCY : 'Emergency Alarm',
        ALARM_FULL_FREEZE : 'Freeze Alarm',
        ALARM_FULL_GAS : 'Gas Alarm',
        ALARM_FULL_HEAT : 'Heat Alarm',
        ALARM_FULL_WATER : 'Water Alarm',
        ALARM_FULL_FIRE_SUPERVISORY : 'Fire Supervisory',
        ALARM_FULL_FIRE_VERIFY : 'Verify Fire'
    }

    CHIME_MODE_OFF = 0b0000
    CHIME_MODE_SINGLE_BEEP = 0b0001
    CHIME_MODE_CONSTANT_BEEP = 0b0010
    CHIME_MODE_BOTH_BEEP = 0b0011
    CHIME_MODE_CHIME = 0b1000
    CHIME_MODE_CHIME_SINGLE_BEEP = 0b1001
    CHIME_MODE_CHIME_CONSTANT_BEEP = 0b1010
    CHIME_MODE_CHIME_BOTH_BEEP = 0b1011

    CHIME_MODE_STR = {
        CHIME_MODE_OFF : 'Silent',
        CHIME_MODE_SINGLE_BEEP : 'Single Beep',
        CHIME_MODE_CONSTANT_BEEP : 'Constantly Beeping',
        CHIME_MODE_BOTH_BEEP : 'Single Beep while Constantly Beeping',
        CHIME_MODE_CHIME : 'Single Chime',
        CHIME_MODE_CHIME_SINGLE_BEEP : 'Single Chime with Single Beep',
        CHIME_MODE_CHIME_CONSTANT_BEEP : 'Single Chime with Constantly Beeping',
        CHIME_MODE_CHIME_BOTH_BEEP : 'Single Chime with Single Beep and Constantly Beeping'
    }

    _status = 0
    _arm_up = 0
    _alarm = 0
    _chime_mode = 0   
    _timer_entrance_1 = 0
    _timer_entrance_2 = 0
    _timer_exit_1 = 0
    _timer_exit_2 = 0
    _number = 0
    _updated_at = 0

    def __init__(self, pyelk = None):
        self._pyelk = pyelk

    """
    PyElk.Event.EVENT_ARMING_STATUS_REPORT
    """
    def unpack_event_arming_status_report(self, event):
        status = event.data_dehex()[self._number-1]
        arm_up = event.data_dehex()[8+self._number-1]
        alarm = event.data_dehex(True)[16+self._number-1]
        if ((self._status == status) and (self._arm_up == arm_up) and (self._alarm == alarm)):
            return
        self._status = status
        self._arm_up = arm_up
        self._alarm = alarm
        self._updated_at = event._time

    """
    PyElk.Event.EVENT_ENTRY_EXIT_TIMER
    """
    def unpack_event_entry_exit_timer(self, event):
        if (event._data[0] == '1'):
            is_entrance = True
        else:
            is_enrtance = False
        timer_1 = int(event._data_str[1:3])
        timer_2 = int(event._data_str[4:6])
        status = event.data_dehex(True)[7]
        self._status = status
        if is_entrance:
            self._timer_entrance_1 = timer_1
            self._timer_entrance_2 = timer_2
        else:
            self._timer_exit_1 = timer_1
            self._timer_exit_2 = timer_2
        self._updated_at = event._time

    def age(self):
        return time.time() - self._updated_at

    def status(self):
        return self.STATUS_STR[self._status]

    def arm_up(self):
        return self.ARM_UP_STR[self._arm_up]

    def alarm(self):
        return self.ALARM_STR[self._alarm]

    def chime_mode(self):
        return self._CHIME_MODE_STR(self._chime_mode)

