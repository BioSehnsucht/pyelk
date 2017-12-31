"""Elk Area."""
from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Const import *
from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class Area(Node):
    """Represents an Area in the Elk."""

    STATUS_DISARMED = 0
    STATUS_ARMED_AWAY = 1
    STATUS_ARMED_STAY = 2
    STATUS_ARMED_STAY_INSTANT = 3
    STATUS_ARMED_NIGHT = 4
    STATUS_ARMED_NIGHT_INSTANT = 5
    STATUS_ARMED_VACATION = 6
    STATUS_ALARM_PENDING = 7
    STATUS_ALARM_TRIGGERED = 8
    STATUS_TIMER_ENTRY = 9
    STATUS_TIMER_EXIT = 10

    STATUS_STR = {
        STATUS_DISARMED : 'Disarmed',
        STATUS_ARMED_AWAY : 'Armed Away',
        STATUS_ARMED_STAY : 'Armed Stay',
        STATUS_ARMED_STAY_INSTANT : 'Armed Stay Instant',
        STATUS_ARMED_NIGHT : 'Armed to Night',
        STATUS_ARMED_NIGHT_INSTANT : 'Armed to Night Instant',
        STATUS_ARMED_VACATION : 'Armed to Vacation',
        STATUS_ALARM_PENDING : 'Alarm Pending',
        STATUS_ALARM_TRIGGERED : 'Alarm Triggered',
        STATUS_TIMER_ENTRY : 'Entry Timer Running',
        STATUS_TIMER_EXIT : 'Exit Timer Running',
    }

    ARM_DISARM = 0
    ARM_AWAY = 1
    ARM_STAY = 2
    ARM_STAY_INSTANT = 3
    ARM_NIGHT = 4
    ARM_NIGHT_INSTANT = 5
    ARM_VACATION = 6
    ARM_NEXT_AWAY = 7
    ARM_NEXT_STAY = 8
    ARM_FORCE_AWAY = 9
    ARM_FORCE_STAY = 10

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
        ARM_UP_READY_VIOLATED_BYPASS : 'Ready To Arm, but a zone violated and can be Force Armed',
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

    def __init__(self, pyelk=None, number=None):
        """Initializes Area object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super().__init__('Area', pyelk, number)
        # Initialize Area specific things
        self._last_user_num = 0
        self._last_user_at = 0
        self._last_user_name = 'N/A'
        self._last_disarmed_at = 0
        self._last_armed_at = 0
        self._last_keypad_num = 0
        self._last_keypad_name = ''
        self._arm_up = 0
        self._alarm = 0
        self._alarm_memory = False
        self._chime_mode = 0
        self._timer_entrance_1 = 0
        self._timer_entrance_2 = 0
        self._timer_exit_1 = 0
        self._timer_exit_2 = 0
        self._member_zone = []
        self._member_keypad = []
        for node_index in range(0, ZONE_MAX_COUNT):
            self._member_zone.append(False)
        for node_index in range(0, KEYPAD_MAX_COUNT):
            self._member_keypad.append(False)

    def description_pretty(self, prefix='Area '):
        """Area description, as text string (auto-generated if not set)."""
        return super().description_pretty(prefix)

    def dump(self):
        """Dump debugging data, to be removed."""
        _LOGGER.debug('Area Status: ' + str(repr(self.status_pretty())))
        _LOGGER.debug('Area Arm Up: ' + str(repr(self.arm_up_pretty())))
        _LOGGER.debug('Area Alarm: ' + str(repr(self.alarm_pretty())))
        _LOGGER.debug('Area Description: ' + str(repr(self.description_pretty())))

    @property
    def alarm_active(self):
        """True if Area is actively alarming."""
        if self._alarm != self.ALARM_NONE:
            return True
        return False

    @property
    def timers_active(self):
        """Which if any Entry / Exit timers are active."""
        if self._timer_entrance_1 > 0:
            return self.STATUS_TIMER_ENTRY
        elif self._timer_entrance_2 > 0:
            return self.STATUS_TIMER_ENTRY
        elif self._timer_exit_1 > 0:
            return self.STATUS_TIMER_EXIT
        elif self._timer_exit_2 > 0:
            return self.STATUS_TIMER_EXIT
        return False

    @property
    def member_keypad(self):
        """Returns list of keypads and whether they are a member of this Area."""
        return self._member_keypad

    @member_keypad.setter
    def member_keypad(self, value):
        """Sets list of keypads and whether they are a member of this Area."""
        self._member_keypad = value

    @property
    def member_zone(self):
        """Returns list of zones and whether they are a member of this Area."""
        return self._member_zone

    @member_zone.setter
    def member_zone(self, value):
        """Sets list of zones and whether they are a member of this Area."""
        self._member_zone = value

    @property
    def last_user_num(self):
        """Returns last user number."""
        return self._last_user_num

    @last_user_num.setter
    def last_user_num(self, value):
        """Sets last user number."""
        self._last_user_num = value

    @property
    def last_user_at(self):
        """Returns last user access at timestamp."""
        return self._last_user_at

    @last_user_at.setter
    def last_user_at(self, value):
        """Sets last user access at timestemp."""
        self._last_user_at = value

    @property
    def last_user_name(self):
        """Returns last user name."""
        return self._last_user_name

    @last_user_name.setter
    def last_user_name(self, value):
        """Sets last user name."""
        self._last_user_name = value

    @property
    def last_disarmed_at(self):
        """Returns last disarmed timestamp."""
        return self._last_disarmed_at

    @last_disarmed_at.setter
    def last_disarmed_at(self, value):
        """Sets last disarmed timestamp."""
        self._last_disarmed_at = value

    @property
    def last_armed_at(self):
        """Returns last armed timestamp."""
        return self._last_armed_at

    @last_armed_at.setter
    def last_armed_at(self, value):
        """Sets last armed timestamp."""
        self._last_armed_at = value

    @property
    def last_keypad_num(self):
        """Returns last keypad number used in Area."""
        return self._last_keypad_num

    @last_keypad_num.setter
    def last_keypad_num(self, value):
        """Sets last keypad number used in Area."""
        self._last_keypad_num = value

    @property
    def last_keypad_name(self):
        """Returns last keypad name used."""
        return self._last_keypad_name

    @last_keypad_name.setter
    def last_keypad_name(self, value):
        """Sets last keypad name used."""
        self._last_keypad_name = value

    @property
    def chime_mode(self):
        """Returns chime and beep state."""
        return self._chime_mode

    @chime_mode.setter
    def chime_mode(self, value):
        """Sets chime and beep state."""
        self._chime_mode = value

    @property
    def arm_up(self):
        """Returns "arm up" (readiness) status."""
        return self._arm_up

    @property
    def member_zones_count(self):
        """Number of Zones which are a member of this Area."""
        count = 0
        for node_index in range(0, ZONE_MAX_COUNT):
            if self._member_zone[node_index] is True:
                count += 1
        return count

    @property
    def member_keypads_count(self):
        """Number of Keypads which are a member of this Area."""
        count = 0
        for k in range(0, KEYPAD_MAX_COUNT):
            if self._member_keypad[k] is True:
                count += 1
        return count

    def arm_up_pretty(self):
        """Area's Arm Up (arming readiness) state as text string."""
        return self.ARM_UP_STR[self._arm_up]

    def alarm_pretty(self):
        """Area's Alarm state as text string."""
        return self.ALARM_STR[self._alarm]

    def chime_mode_pretty(self):
        """Area's Chime Mode as text string."""
        return self.CHIME_MODE_STR[self._chime_mode]

    def arm(self, desired_arm_level, user_code):
        """Attempt to arm Area to specified arm mode.

        desired_arm_level: Arming level to attempt to set.
        user_code: User code to use for the arming attempt.

        """
        event = Event()
        if desired_arm_level == self.ARM_DISARM:
            event.type = Event.EVENT_DISARM
        elif desired_arm_level == self.ARM_AWAY:
            event.type = Event.EVENT_ARM_AWAY
        elif desired_arm_level == self.ARM_STAY:
            event.type = Event.EVENT_ARM_STAY
        elif desired_arm_level == self.ARM_STAY_INSTANT:
            event.type = Event.EVENT_ARM_STAY_INSTANT
        elif desired_arm_level == self.ARM_NIGHT:
            event.type = Event.EVENT_ARM_NIGHT
        elif desired_arm_level == self.ARM_NIGHT_INSTANT:
            event.type = Event.EVENT_ARM_NIGHT_INSTANT
        elif desired_arm_level == self.ARM_VACATION:
            event.type = Event.EVENT_ARM_VACATION
        elif desired_arm_level == self.ARM_NEXT_AWAY:
            event.type = Event.EVENT_ARM_NEXT_AWAY
        elif desired_arm_level == self.ARM_NEXT_STAY:
            event.type = Event.EVENT_ARM_NEXT_STAY
        elif desired_arm_level == self.ARM_FORCE_AWAY:
            event.type = Event.EVENT_ARM_FORCE_AWAY
        elif desired_arm_level == self.ARM_FORCE_STAY:
            event.type = Event.EVENT_ARM_FORCE_STAY
        # rjust used to make sure 4 digit codes are formatted as 00XXXX
        event.data_str = str(self._number) + str(user_code).rjust(6, '0')
        self._pyelk.elk_event_send(event)
        return

    def disarm(self, user_code):
        """Attempt to disarm Area.

        This is a shortcut for arm(Area.ARM_DISARM, user_code).

        user_code: User code to use for the arming attempt.
        """
        return self.arm(self.ARM_DISARM, user_code)

    def unpack_event_arming_status_report(self, event):
        """Unpack EVENT_ARMING_STATUS_REPORT.

        Event data format: SSSSSSSSUUUUUUUUAAAAAAAA
        S[8]: Array of 8 area armed status
        U[8]: Array of 8 area arm up state
        A[8]: Array of 8 area alarm state
        """
        status = event.data_dehex()[self._index]
        arm_up = event.data_dehex()[8+self._index]
        alarm = event.data_dehex(True)[16+self._index]
        if (self._status == status) and (self._arm_up == arm_up) and (self._alarm == alarm):
            return
        self._status = status
        # Hopefully it never takes more than a second to get from
        # EVENT_USER_CODE_ENTERED to EVENT_ARMING_STATUS_REPORT
        if (event.time - self._last_user_at) < 1.0:
            if self._status == self.STATUS_DISARMED:
                self._last_disarmed_at = event.time
            else:
                self._last_armed_at = event.time
        self._arm_up = arm_up
        self._alarm = alarm
        self._updated_at = event.time
        self._callback()

    def unpack_event_entry_exit_timer(self, event):
        """Unpack EVENT_ENTRY_EXIT_TIMER.

        Event data format: ADtttTTTS
        A: Area, '1' to '8' (ASCII decimal)
        D: Data type, '0' for Exit, '1' for Entrance (ASCII decimal)
        ttt: Timer 1 value in seconds, range '000' to '255' seconds (ASCII decimal)
        TTT: Timer 2 value in seconds, range '000' to '255' seconds (ASCII decimal)
        S: Armed state
        """
        # Determine if this is Entrance or Exit timer update
        is_entrance = None
        if event.data[0] == '1':
            is_entrance = True
        else:
            is_entrance = False
        timer_1 = int(event.data_str[1:3])
        timer_2 = int(event.data_str[4:6])
        status = event.data_dehex(True)[7]
        self._status = status
        if is_entrance:
            self._timer_entrance_1 = timer_1
            self._timer_entrance_2 = timer_2
        else:
            self._timer_exit_1 = timer_1
            self._timer_exit_2 = timer_2
        self._updated_at = event.time
        self._callback()

    def unpack_event_alarm_memory(self, event):
        """Unpack EVENT_ALARM_MEMORY.

        Event data format: SSSSSSS
        S[8]: Alarm memory for each of 8 Areas, 0 if no memory, 1 if memory
        """
        data = event.data_str[self._index]
        if data == '1':
            self._alarm_memory = True
        else:
            self._alarm_memory = False
        self._updated_at = event.time
        self._callback()
