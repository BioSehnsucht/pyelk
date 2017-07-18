from collections import namedtuple
from collections import deque
import logging
import time
import traceback
from ..Node import Node

_LOGGER = logging.getLogger(__name__)

class Zone(Node):
    # Possible (input) States for a Zone
    STATE_UNCONFIGURED = 0
    STATE_OPEN = 1
    STATE_EOL = 2
    STATE_SHORT = 3

    # Possible Statuses for a Zone
    STATUS_NORMAL = 0
    STATUS_TROUBLE = 1
    STATUS_VIOLATED = 2
    STATUS_BYPASSED = 3

    # Possible Definitions (types) for a Zone
    DEFINITION_DISABLED = 0
    DEFINITION_BURGLAR_1 = 1
    DEFINITION_BURGLAR_2 = 2
    DEFINITION_BURGLAR_PERIMETER_INSTANT = 3
    DEFINITION_BURGLAR_INTERIOR = 4
    DEFINITION_BURGLAR_INTERIOR_FOLLOWER = 5
    DEFINITION_BURGLAR_INTERIOR_NIGHT = 6
    DEFINITION_BURGLAR_INTERIOR_NIGHT_DELAY = 7
    DEFINITION_BURGLAR_24_HOUR = 8
    DEFINITION_BURGLAR_BOX_TAMPER = 9
    DEFINITION_FIRE_ALARM = 10
    DEFINITION_FIRE_VERIFIED = 11
    DEFINITION_FIRE_SUPERVISORY = 12
    DEFINITION_AUX_ALARM_1 = 13
    DEFINITION_AUX_ALARM_2 = 14
    DEFINITION_KEYFOB = 15
    DEFINITION_NON_ALARM = 16
    DEFINITION_CARBON_MONOXIDE = 17
    DEFINITION_EMERGENCY_ALARM = 18
    DEFINITION_FREEZE_ALARM = 19
    DEFINITION_GAS_ALARM = 20
    DEFINITION_HEAT_ALARM = 21
    DEFINITION_MEDICAL_ALARM = 22
    DEFINITION_POLICE_ALARM = 23
    DEFINITION_POLICE_NO_INDICATION = 24
    DEFINITION_WATER_ALARM = 25
    DEFINITION_KEY_MOMENTARY_ARM_DISARM = 26
    DEFINITION_KEY_MOMENTARY_ARM_AWAY = 27
    DEFINITION_KEY_MOMENTARY_ARM_STAY = 28
    DEFINITION_KEY_MOMENTARY_DISARM = 29
    DEFINITION_KEY_ON_OFF = 30
    DEFINITION_MUTE_AUDIBLES = 31
    DEFINITION_POWER_SUPERVISORY = 32
    DEFINITION_TEMPERATURE = 33
    DEFINITION_ANALOG_ZONE = 34
    DEFINITION_PHONE_KEY = 35
    DEFINITION_INTERCOM_KEY = 36

    # Possible Alarm configurations for a Zone
    ALARM_DISABLED = 0
    ALARM_BURGLAR_1 = 1
    ALARM_BURGLAR_2 = 2
    ALARM_BURGLAR_PERIMETER_INSTANT = 3
    ALARM_BURGLAR_INTERIOR = 4
    ALARM_BURGLAR_INTERIOR_FOLLOWER = 5
    ALARM_BURGLAR_INTERIOR_NIGHT = 6
    ALARM_BURGLAR_INTERIOR_NIGHT_DELAY = 7
    ALARM_BURGLAR_24_HOUR = 8
    ALARM_BURGLAR_BOX_TAMPER = 9
    ALARM_FIRE_ALARM = 10
    ALARM_FIRE_VERIFIED = 11
    ALARM_FIRE_SUPERVISORY = 12
    ALARM_AUX_ALARM_1 = 13
    ALARM_AUX_ALARM_2 = 14
    ALARM_KEYFOB = 15
    ALARM_NON_ALARM = 16
    ALARM_CARBON_MONOXIDE = 17
    ALARM_EMERGENCY_ALARM = 18
    ALARM_FREEZE_ALARM = 19
    ALARM_GAS_ALARM = 20
    ALARM_HEAT_ALARM = 21
    ALARM_MEDICAL_ALARM = 22
    ALARM_POLICE_ALARM = 23
    ALARM_POLICE_NO_INDICATION = 24
    ALARM_WATER_ALARM = 25

    # Text strings for States
    STATE_STR = {
        STATE_UNCONFIGURED : 'Unconfigured',
        STATE_OPEN : 'Open',
        STATE_EOL : 'EOL',
        STATE_SHORT : 'Short'
        }

    # Text strings for Statuses
    STATUS_STR = {
        STATUS_NORMAL : 'Normal',
        STATUS_TROUBLE : 'Trouble',
        STATUS_VIOLATED : 'Violated',
        STATUS_BYPASSED : 'Bypassed'
        }

    # Text strings for Definitions
    DEFINITION_STR = {
        DEFINITION_DISABLED : 'Disabled',
        DEFINITION_BURGLAR_1 : 'Burglar Entry/Exit 1',
        DEFINITION_BURGLAR_2 : 'Burglar Entry/Exit 2',
        DEFINITION_BURGLAR_PERIMETER_INSTANT : 'Burglar Perimeter Instant',
        DEFINITION_BURGLAR_INTERIOR : 'Burgler Interior',
        DEFINITION_BURGLAR_INTERIOR_FOLLOWER : 'Burgler Interior Follower',
        DEFINITION_BURGLAR_INTERIOR_NIGHT : 'Burgler Interior Night',
        DEFINITION_BURGLAR_INTERIOR_NIGHT_DELAY : 'Burglar Interior Night Delay',
        DEFINITION_BURGLAR_24_HOUR : 'Burglar 24 Hour',
        DEFINITION_BURGLAR_BOX_TAMPER : 'Burglar Box Tamper',
        DEFINITION_FIRE_ALARM : 'Fire Alarm',
        DEFINITION_FIRE_VERIFIED : 'Fire Verified',
        DEFINITION_FIRE_SUPERVISORY : 'Fire Supervisory',
        DEFINITION_AUX_ALARM_1 : 'Aux Alarm 1',
        DEFINITION_AUX_ALARM_2 : 'Aux Alarm 2',
        DEFINITION_KEYFOB : 'Keyfob',
        DEFINITION_NON_ALARM : 'Non Alarm',
        DEFINITION_CARBON_MONOXIDE : 'Carbon Monoxide',
        DEFINITION_EMERGENCY_ALARM : 'Emergency Alarm',
        DEFINITION_FREEZE_ALARM : 'Freeze Alarm',
        DEFINITION_GAS_ALARM : 'Gas Alarm',
        DEFINITION_HEAT_ALARM : 'Heat Alarm',
        DEFINITION_MEDICAL_ALARM : 'Medical Alarm',
        DEFINITION_POLICE_ALARM : 'Police Alarm',
        DEFINITION_POLICE_NO_INDICATION : 'Police No Indication',
        DEFINITION_WATER_ALARM : 'Water Alarm',
        DEFINITION_KEY_MOMENTARY_ARM_DISARM : 'Key Momentary Arm / Disarm',
        DEFINITION_KEY_MOMENTARY_ARM_AWAY : 'Key Momentary Arm Away',
        DEFINITION_KEY_MOMENTARY_ARM_STAY : 'Key Momentary Arm Stay',
        DEFINITION_KEY_MOMENTARY_DISARM : 'Key Momentary Disarm',
        DEFINITION_KEY_ON_OFF : 'Key On/Off',
        DEFINITION_MUTE_AUDIBLES : 'Mute Audibles',
        DEFINITION_POWER_SUPERVISORY : 'Power Supervisory',
        DEFINITION_TEMPERATURE : 'Temperature',
        DEFINITION_ANALOG_ZONE : 'Analog Zone',
        DEFINITION_PHONE_KEY : 'Phone Key',
        DEFINITION_INTERCOM_KEY : 'Intercom Key'
        }

    # Test strings for Alarm configurations
    ALARM_STR = {
        ALARM_DISABLED : 'Disabled',
        ALARM_BURGLAR_1 : 'Burglar Entry/Exit 1',
        ALARM_BURGLAR_2 : 'Burglar Entry/Exit 2',
        ALARM_BURGLAR_PERIMETER_INSTANT : 'Burglar Perimeter Instant',
        ALARM_BURGLAR_INTERIOR : 'Burgler Interior',
        ALARM_BURGLAR_INTERIOR_FOLLOWER : 'Burgler Interior Follower',
        ALARM_BURGLAR_INTERIOR_NIGHT : 'Burgler Interior Night',
        ALARM_BURGLAR_INTERIOR_NIGHT_DELAY : 'Burglar Interior Night Delay',
        ALARM_BURGLAR_24_HOUR : 'Burglar 24 Hour',
        ALARM_BURGLAR_BOX_TAMPER : 'Burglar Box Tamper',
        ALARM_FIRE_ALARM : 'Fire Alarm',
        ALARM_FIRE_VERIFIED : 'Fire Verified',
        ALARM_FIRE_SUPERVISORY : 'Fire Supervisory',
        ALARM_AUX_ALARM_1 : 'Aux Alarm 1',
        ALARM_AUX_ALARM_2 : 'Aux Alarm 2',
        ALARM_KEYFOB : 'Keyfob',
        ALARM_NON_ALARM : 'Non Alarm',
        ALARM_CARBON_MONOXIDE : 'Carbon Monoxide',
        ALARM_EMERGENCY_ALARM : 'Emergency Alarm',
        ALARM_FREEZE_ALARM : 'Freeze Alarm',
        ALARM_GAS_ALARM : 'Gas Alarm',
        ALARM_HEAT_ALARM : 'Heat Alarm',
        ALARM_MEDICAL_ALARM : 'Medical Alarm',
        ALARM_POLICE_ALARM : 'Police Alarm',
        ALARM_POLICE_NO_INDICATION : 'Police No Indication',
        ALARM_WATER_ALARM : 'Water Alarm'
        }

    def __init__(self, pyelk=None, number=None):
        """Initializes Zone object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super().__init__(pyelk, number)
        # Initialize Zone specific things
        self._state = 0
        self._definition = 0
        self._alarm = 0
        self._voltage = 0.0
        self._temp = -460

    @property
    def temp(self):
        return self._temp

    @property
    def definition(self):
        return self._definition

    @definition.setter
    def definition(self, value):
        self._definition = value

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._state = value

    @property
    def alarm(self):
        return self._alarm

    @alarm.setter
    def alarm(self, value):
        self._alarm = value

    def description_pretty(self, prefix='Zone '):
        """Output description, as text string (auto-generated if not set)."""
        return super().description_pretty(prefix)

    def state_pretty(self):
        """Zone's current State as text string."""
        return self.STATE_STR[self._state]

    def alarm_pretty(self):
        """Zone's Alarm type configuration as text string."""
        return self.ALARM_STR[self._alarm]

    def definition_pretty(self):
        """Zone's Definition type configuration as text string."""
        return self.DEFINITION_STR[self._definition]

    def dump(self):
        """Dump debugging data, to be removed."""
        _LOGGER.debug('Zone State: ' + str(repr(self.state_pretty())))
        _LOGGER.debug('Zone Status: ' + str(repr(self.status_pretty())))
        _LOGGER.debug('Zone Definition: ' + str(repr(self.definition_pretty())))
        _LOGGER.debug('Zone Description: ' + str(repr(self.description_pretty())))

    def unpack_event_alarm_zone(self, event):
        """Unpack EVENT_ALARM_ZONE_REPORT.

        Event data format: Z[208]
        Z[208]: Array of 208 bytes showing alarm by zone
        """
        data = event.data_dehex(True)[self._number-1]
        if self._alarm == data:
            return
        self._alarm = data
        self._updated_at = event.time
        self._callback()

    def unpack_event_zone_definition(self, event):
        """Unpack EVENT_ZONE_DEFINITION_REPLY.

        Event data format: D[208]
        D[208]: Array of all 208 zones with the zone definition
        """
        data = event.data_dehex(True)[self._number-1]
        if self._definition == data:
            return
        self._definition = data
        if (self._state == self.STATE_UNCONFIGURED)\
        and (self._definition == self.DEFINITION_DISABLED):
            self._enabled = False
        else:
            self._enabled = True
        self._updated_at = event.time
        self._callback()

    def unpack_event_zone_partition(self, event):
        """Unpack EVENT_ZONE_PARTITION_REPORT.

        Event data format: D[208]
        D[208]: Array of all 208 zones with the partition for each zone
        """
        data = event.data_dehex(True)[self._number-1]
        self._area = data
        for node_index in range(1, 9):
            self._pyelk.AREAS[node_index].member_zone[self._number] = False
        if self._area > 0:
            self._pyelk.AREAS[self._area].member_zone[self._number] = True
        self._updated_at = event.time
        self._callback()

    def unpack_event_zone_voltage(self, event):
        """Unpack EVENT_ZONE_VOLTAGE_REPLY.

        Event data format: ZZZDDD
        ZZZ: Zone number '001' to '208' (ASCII decimal)
        DDD: Zone voltage data as 3 ACII decimal characters, actual value is DD.D (divide by 10)
        """
        data = int(event.data_str[2:4]) / 10.0
        if self._voltage == data:
            return
        self._voltage = data
        self._updated_at = event.time
        self._callback()

    def unpack_event_zone_status_report(self, event):
        """Unpack EVENT_ZONE_STATUS_REPORT.

        Event data format: D[208]
        D[208]: Array of all 208 zones with status as hexadecimal value
        """
        data = int(event.data_dehex()[self._number-1])
        state = data & 0b11
        status = (data & 0b1100) >> 2
        if (self._state == state) and (self._status == status):
            return
        self._state = state
        self._status = status
        if (self._state == self.STATE_UNCONFIGURED)\
        and (self._definition == self.DEFINITION_DISABLED):
            self._enabled = False
        else:
            self._enabled = True
        self._updated_at = event.time
        self._callback()

    def unpack_event_zone_update(self, event):
        """Unpack EVENT_ZONE_UPDATE.

        Event data format: ZZZS
        ZZZ: Zone number '001' to '208' (ASCII decimal)
        S: Status as hexadecimal value
        """
        data = int(event.data_dehex()[3])
        state = data & 0b11
        status = (data & 0b1100) >> 2
        if (self._state == state) and (self._status == status):
            return
        self._state = state
        self._status = status
        self._updated_at = event.time
        self._callback()

    def unpack_event_temp_request_reply(self, event):
        """Unpack EVENT_TEMP_REQUEST_REPLY.

        Event data format: GNNDDD
        G: Requested Group ('0')
        NN: Device number in group (2 decimal ASCII digits)
        DDD: Temperature in ASCII decimal (offset by -60 for true value)
        """
        data = int(event.data_str[3:6])
        data = data - 60
        self._temp = data
        self._updated_at = event.time
        self._callback()
