from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class Area(Node):
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

    def __init__(self, pyelk = None, number = None):
        """Initializes Area object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super(Area, self).__init__(pyelk, number)
        # Initialize Area specific things
        self._last_user_code = 0
        self._last_user_at = 0
        self._last_disarmed_by_user = 0
        self._last_disarmed_at = 0
        self._last_armed_by_user = 0
        self._last_armed_at = 0
        self._arm_up = 0
        self._alarm = 0
        self._chime_mode = 0
        self._timer_entrance_1 = 0
        self._timer_entrance_2 = 0
        self._timer_exit_1 = 0
        self._timer_exit_2 = 0
        self._member_zone = []
        self._member_keypad = []
        for z in range(0,209):
            self._member_zone.append(False)
        for k in range(0,17):
            self._member_keypad.append(False)

    def description(self):
        """Area description, as text string (auto-generated if not set)."""
        return super(Area, self).description('Area ')

    @property
    def alarm_active(self):
        """True if Area is actively alarming."""
        if self._alarm != self.ALARM_NONE:
            return True
        else:
            return False

    @property
    def timers_active(self):
        """True if any Entry / Exit timers are active."""
        if self._timer_entrance_1 > 0:
            return True
        elif self._timer_entrance_2 > 0:
            return True
        elif self._timer_exit_1  > 0:
            return True
        elif self._timer_exit_2 > 0:
            return True
        else:
            return False

    @property
    def member_zones(self):
        """Number of Zones which are a member of this Area."""
        count = 0
        for z in range(0,209):
            if self._member_zone[z] == True:
                count += 1
        return count

    @property
    def member_keypads(self):
        """Number of Keypads which are a member of this Area."""
        count = 0
        for k in range(0,17):
            if self._member_keypad[k] == True:
                count += 1
        return count

    def arm_up(self):
        """Area's Arm Up (arming readiness) state as text string."""
        return self.ARM_UP_STR[self._arm_up]

    def alarm(self):
        """Area's Alarm state as text string."""
        return self.ALARM_STR[self._alarm]

    def chime_mode(self):
        """Area's Chime Mode as text string."""
        return self._CHIME_MODE_STR(self._chime_mode)

    def arm(self, desired_arm_level, user_code):
        """Attempt to arm Area to specified arm mode.

        desired_arm_level: Arming level to attempt to set.
        user_code: User code to use for the arming attempt.

        """
        event = Event()
        if (desired_arm_level == self.ARM_DISARM):
            event._type = Event.EVENT_DISARM
        elif (desired_arm_level == self.ARM_AWAY):
            event._type = Event.EVENT_ARM_AWAY
        elif (desired_arm_level == self.ARM_STAY):
            event._type = Event.EVENT_ARM_STAY
        elif (desired_arm_level == self.ARM_STAY_INSTANT):
            event._type = Event.EVENT_ARM_STAY_INSTANT
        elif (desired_arm_level == self.ARM_NIGHT):
            event._type = Event.EVENT_ARM_NIGHT
        elif (desired_arm_level == self.ARM_NIGHT_INSTANT):
            event._type = Event.EVENT_ARM_NIGHT_INSTANT
        elif (desired_arm_level == self.ARM_VACATION):
            event._type = Event.EVENT_ARM_VACATION
        elif (desired_arm_level == self.ARM_NEXT_AWAY):
            event._type = Event.EVENT_ARM_NEXT_AWAY
        elif (desired_arm_level == self.ARM_NEXT_STAY):
            event._type = Event.EVENT_ARM_NEXT_STAY
        elif (desired_arm_level == self.ARM_FORCE_AWAY):
            event._type = Event.EVENT_ARM_FORCE_AWAY
        elif (desired_arm_level == self.ARM_FORCE_STAY):
            event._type = Event.EVENT_ARM_FORCE_STAY
        # rjust used to make sure 4 digit codes are formatted as 00XXXX
        event._data_str = str(self._number) + str(user_code).rjust(6,'0')
        self._pyelk.elk_event_send(event)
        return

    def disarm(self, user_code):
        """Attempt to disarm Area.

        This is a shortcut for arm(Area.ARM_DISARM, user_code).

        user_code: User code to use for the arming attempt.
        """
        return self.arm(self.ARM_DISARM, user_code)

    def unpack_event_arming_status_report(self, event):
        """Unpack EVENT_ARMING_STATUS_REPORT."""
        status = event.data_dehex()[self._number-1]
        arm_up = event.data_dehex()[8+self._number-1]
        alarm = event.data_dehex(True)[16+self._number-1]
        if ((self._status == status) and (self._arm_up == arm_up) and (self._alarm == alarm)):
            return
        self._status = status
        # Hopefully it never takes more than a second to get from
        # EVENT_USER_CODE_ENTERED to EVENT_ARMING_STATUS_REPORT
        if (event._time - self._last_user_at) < 1.0:
            if self._status == self.STATUS_DISARMED:
                self._last_disarmed_at = event._time
                self._last_disarmed_by_user = self._last_user_code
            else:
                self._last_armed_at = event._time
                self._last_armed_by_user = self._last_user_code
        self._arm_up = arm_up
        self._alarm = alarm
        self._updated_at = event._time
        self._callback()

    def unpack_event_entry_exit_timer(self, event):
        """Unpack EVENT_ENTRY_EXIT_TIMER."""
        # Determine if this is Entrance or Exit timer update
        is_entrance = None
        if (event._data[0] == '1'):
            is_entrance = True
        else:
            is_entrance = False
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
        self._callback()
