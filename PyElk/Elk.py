"""Implementation of the main PyElk class, which is the interface used to
initiate and control communications with the Elk device.
"""
from collections import deque
import logging
import time
import traceback
import serial
import serial.threaded

from .Area import Area
from .Event import Event
from .Keypad import Keypad
from .Output import Output
from .Task import Task
from .Thermostat import Thermostat
from .X10 import X10
from .Zone import Zone

_LOGGER = logging.getLogger(__name__)

# Events automatically handled under normal circumstances
# by elk_process_event
EVENT_LIST_AUTO_PROCESS = [
    Event.EVENT_INSTALLER_ELKRP,
    Event.EVENT_INSTALLER_EXIT,
    Event.EVENT_TROUBLE_STATUS_REPLY,
    Event.EVENT_ALARM_MEMORY,
    Event.EVENT_ENTRY_EXIT_TIMER,
    Event.EVENT_USER_CODE_ENTERED,
    Event.EVENT_TASK_UPDATE,
    Event.EVENT_OUTPUT_UPDATE,
    Event.EVENT_ZONE_UPDATE,
    Event.EVENT_KEYPAD_STATUS_REPORT,
    Event.EVENT_ETHERNET_TEST,
    Event.EVENT_ARMING_STATUS_REPORT,
    Event.EVENT_ALARM_ZONE_REPORT,
    Event.EVENT_TEMP_REQUEST_REPLY,
    Event.EVENT_THERMOSTAT_DATA_REPLY,
    Event.EVENT_PLC_CHANGE_UPDATE,
    Event.EVENT_VERSION_REPLY,
    ]

# Events specifically NOT handled automatically by elk_process_event
# while rescan is in progress
EVENT_LIST_RESCAN_BLACKLIST = [
    Event.EVENT_ALARM_ZONE_REPORT,
    Event.EVENT_ARMING_STATUS_REPORT,
    Event.EVENT_OUTPUT_STATUS_REPORT,
    Event.EVENT_OUTPUT_UPDATE,
    Event.EVENT_KEYPAD_AREA_REPLY,
    Event.EVENT_KEYPAD_STATUS_REPORT,
    Event.EVENT_ZONE_DEFINITION_REPLY,
    Event.EVENT_ZONE_PARTITION_REPORT,
    Event.EVENT_ZONE_STATUS_REPORT,
    Event.EVENT_ZONE_UPDATE,
    Event.EVENT_ZONE_VOLTAGE_REPLY,
    Event.EVENT_TEMP_REQUEST_REPLY,
    Event.EVENT_THERMOSTAT_DATA_REPLY,
    Event.EVENT_PLC_STATUS_REPLY,
    ]


class LineHandler(serial.threaded.LineReader):
    """LaneHandler implementation for serial.threaded."""
    _pyelk = None

    def set_pyelk(self, pyelk):
        """Sets the pyelk instance to use."""
        self._pyelk = pyelk

    # Implement Protocol class functions for Threaded Serial
    def connection_made(self, transport):
        """Called when connection is made."""
        _LOGGER.debug('Calling super connection_made')
        super(LineHandler, self).connection_made(transport)
        _LOGGER.debug('Connected')

    def handle_line(self, line):
        """Validate event and add to incoming buffer."""
        self._pyelk.elk_event_enqueue(line)
        _LOGGER.debug('handle_line: ' + line)

    def connection_lost(self, exc):
        """Connection was lost."""
        _LOGGER.debug('Lost connection')
        if exc:
            traceback.print_exc(exc)

class Elk(object):
    """
    This is the main class that handles interaction with the Elk panel

    |  address: String of the IP address of the ELK-M1XEP,
       or device name of the serial device connected to the Elk panel,
       ex: 'socket://192.168.12.34:2101' or '/dev/ttyUSB0'
    |  usercode: String of the user code to authenticate to the Elk panel
    |  log: [optional] Log file class from logging module

    :ivar connected: Read only boolean value indicating if the class is
                     connected to the panel.
    :ivar log: Logger used by the class and its children.
    :ivar zones: :class:`~PyElk.Zones.Zones` manager that interacts with Elk
                 input zones.
    :ivar outputs: :class:`~PyElk.Outputs.Outputs` manager that interacts with
                 outputs.
    :ivar areas: :class:`~PyElk.Areas.Areas` manager that interacts with areas.
    """

    STATE_DISCONNECTED = 0
    STATE_RUNNING = 1
    STATE_SCAN_AREAS = 10
    STATE_SCAN_KEYPADS = 11
    STATE_SCAN_OUTPUTS = 12
    STATE_SCAN_TASKS = 13
    STATE_SCAN_THERMOSTATS = 14
    STATE_SCAN_X10 = 15
    STATE_SCAN_ZONES = 16

    def __init__(self, config, log=None):
        """Initializes Elk object.

        address: Host to connect to in either
        "socket://IP.Add.re.ss:Port" or "/dev/ttyUSB0" format.
        usercode: Alarm user code (not currently used, may be removed).
        log: Logger object to use.
        """
        self._state = self.STATE_DISCONNECTED
        self._events = None
        self._reconnect_thread = None
        self._config = config
        self._queue_incoming_elk_events = deque(maxlen=1000)
        self._queue_exported_events = deque(maxlen=1000)
        self._rescan_in_progress = False
        self._elk_versions = None
        self._connection_protocol = None
        self._connection_thread = None
        self.AREAS = []
        self.KEYPADS = []
        self.OUTPUTS = []
        self.TASKS = []
        self.THERMOSTATS = []
        self.X10 = []
        self.ZONES = []

        if log is None:
            self.log = logging.getLogger(__name__)
            self.log.addHandler(NullHandler())
        else:
            self.log = log

        # Using 0..N+1 and putting None in 0 so we aren't constantly converting between 0
        # and 1 based as often...
        # May change back to 0..N at a later date

        max_range = {
            'zone': 208,
            'output' : 208,
            'area' : 8,
            'keypad' : 16,
            'thermostat' : 16,
            'x10' : 256,
            'task' : 32,
            }

        range_order = {
            0 : 'zone',
            1 : 'output',
            2 : 'area',
            3 : 'keypad',
            4 : 'thermostat',
            5 : 'x10',
            6 : 'task',
            }

        for device_class_num in range_order:
            device_class = range_order[device_class_num]
            include_range = None
            exclude_range = None
            if device_class in self._config:
                if 'include' in self._config[device_class]:
                    include_range = self._list_from_ranges(self._config[device_class]['include'])
                if 'exclude' in self._config[device_class]:
                    exclude_range = self._list_from_ranges(self._config[device_class]['exclude'])
            if include_range is None:
                include_range = range(1, max_range[device_class] + 1)
            if exclude_range is None:
                exclude_range = []
            self.log.debug('PyElk config - ' + device_class + ' include range: %s', include_range)
            self.log.debug('PyElk config - ' + device_class + ' exclude range: %s', exclude_range)
            for device_num in range(0, max_range[device_class] + 1):
                if device_num == 0:
                    device = None
                else:
                    # Create device
                    if device_class == 'zone':
                        device = Zone(self)
                    elif device_class == 'output':
                        device = Output(self)
                    elif device_class == 'area':
                        device = Area(self)
                    elif device_class == 'keypad':
                        device = Keypad(self)
                    elif device_class == 'thermostat':
                        device = Thermostat(self)
                    elif device_class == 'x10':
                        device = X10(self)
                    elif device_class == 'task':
                        device = Task(self)
                    # handle exceptions to general setup
                    if device_class == 'x10':
                        device._house, device.number = device.housecode_from_int(device_num)
                    else:
                        device.number = device_num
                    # perform inclusion/exclusion
                    if device_num in include_range:
                        self.log.debug(device_class + ' ' + str(device_num) + ' included')
                        device.included = True
                    if device_num in exclude_range:
                        self.log.debug(device_class + ' ' + str(device_num) + ' excluded')
                        device.included = False
                # Append device
                if device_class == 'zone':
                    self.ZONES.append(device)
                elif device_class == 'output':
                    self.OUTPUTS.append(device)
                elif device_class == 'area':
                    self.AREAS.append(device)
                elif device_class == 'keypad':
                    self.KEYPADS.append(device)
                elif device_class == 'thermostat':
                    self.THERMOSTATS.append(device)
                elif device_class == 'x10':
                    self.X10.append(device)
                elif device_class == 'task':
                    self.TASKS.append(device)
        try:
            self.connect(self._config['host'])

        except ValueError as exception_error:
            try:
                self.log.error(exception_error.message)
            except AttributeError:
                self.log.error(exception_error.args[0])

        if self.connected:
            self._rescan()

    def __del__(self):
        if self._connection_thread is not None:
            self._connection_thread.close()

    @property
    def connected(self):
        """True if connected to Elk panel."""
        if self._connection_thread:
            return self._connection_thread.alive and self._connection_thread.serial.is_open
        return False

    def connect(self, address):
        """Connect to the Elk panel.

        address: Host to connect to in either
        "socket://IP.Add.re.ss:Port" or "/dev/ttyUSB0" format.
        """
        self._connection = serial.serial_for_url(address, timeout=1)
        self._connection_thread = serial.threaded.ReaderThread(self._connection, LineHandler)
        self._connection_thread.start()
        self._connection_transport, self._connection_protocol = self._connection_thread.connect()
        self._connection_protocol.set_pyelk(self)
        _LOGGER.debug('ReaderThread created')

    def _rescan(self):
        """Rescan all things.

        Normally called on startup, and if the panel has left
        programming mode (via Keypad or ElkRP).
        """
        if self._rescan_in_progress is True:
            return
        self._rescan_in_progress = True
        event = Event()
        event.type = Event.EVENT_VERSION
        self.elk_event_send(event)
        self._state = self.STATE_SCAN_ZONES
        self.scan_zones()
        self._state = self.STATE_SCAN_OUTPUTS
        self.scan_outputs()
        self._state = self.STATE_SCAN_AREAS
        self.scan_areas()
        self._state = self.STATE_SCAN_KEYPADS
        self.scan_keypads()
        self._state = self.STATE_SCAN_TASKS
        self.scan_tasks()
        self._state = self.STATE_SCAN_THERMOSTATS
        self.scan_thermostats()
        self._state = self.STATE_SCAN_X10
        self.scan_x10()
        self._rescan_in_progress = False
        self._state = self.STATE_RUNNING

    def exported_event_enqueue(self, data):
        """Add event to the exported event deque.

        Not actually used yet, may get removed.

        data: Event to place on the deque.
        """
        self._queue_exported_events.append(data)

    def elk_event_send(self, event):
        """Send an Elk event to the Elk.

        event: Event to send to Elk.
        """
        event_str = event.to_string()
        _LOGGER.debug('Sending: {}\n'.format(repr(event_str)))
        self._connection_protocol.write_line(event_str)

    def elk_event_enqueue(self, data):
        """Add event to the incoming event deque.

        data: Event to place on the deque.
        """
        event = Event()
        event.parse(data)
        self._queue_incoming_elk_events.append(event)
        self.update()

    def elk_event_scan(self, event_type, data_match=None, timeout=10):
        """Scan the incoming event deque for specified event type.

        event_type: Event type to look for.
        data_match: If set (either single string or list of strings),
        in addition to matching the event_type, we will also compare
        the event data (up to len(data_match)) and only return an
        event if at least one of the data_match matches the event.
        timeout: Time to wait for new events if none already in deque,
        default is 10 seconds.
        """
        endtime = time.time() + timeout
        event = None
        if (type(data_match) is not list) and (data_match is not None):
            data_match = [data_match]
        while time.time() <= endtime:
            for elem in list(self._queue_incoming_elk_events):
                if elem.type == event_type:
                    event = elem
                    matched = True
                    if data_match is not None:
                        matched = False
                        for match_str in data_match:
                            match_len = len(match_str)
                            data_str = event.data_str[0:match_len]
                            if data_str == match_str:
                                matched = True
                    if matched:
                        self._queue_incoming_elk_events.remove(elem)
                        return event

        _LOGGER.debug('elk_event_scan : timeout')
        return False

    def update(self):
        self.elk_queue_process()

    def elk_queue_process(self):
        """Process the incoming event deque."""
        _LOGGER.debug('elk_queue_process - checking events')
        for event in list(self._queue_incoming_elk_events):
            # Remove stale events over 120 seconds old, normally shouldn't happen
            if event.age() > 120:
                self._queue_incoming_elk_events.remove(event)
                _LOGGER.error('elk_queue_process - removing stale event: ' + str(repr(event.type)))
            elif event.type in EVENT_LIST_AUTO_PROCESS:
                # Event is one we handle automatically
                if (self._rescan_in_progress) and (event.type in EVENT_LIST_RESCAN_BLACKLIST):
                    # Skip for now, scanning may consume the event instead
                    _LOGGER.debug('elk_queue_process - rescan in progress, skipping: '\
                                  + str(repr(event.type)))
                    continue
                else:
                    # Process event
                    self._queue_incoming_elk_events.remove(event)
                    if event.type == Event.EVENT_INSTALLER_EXIT:
                        # Initiate a rescan if the Elk keypad just left
                        # installer mode and break out of the loop
                        # This is also sent immediately after RP disconnects
                        _LOGGER.debug('elk_queue_process - Event.EVENT_INSTALLER_EXIT')
                        # This needs to be spun into another thread probably, or done async
                        self._rescan()
                        return
                    elif event.type == Event.EVENT_INSTALLER_ELKRP:
                        # Consume ElkRP Connect events
                        # but we don't do anything with them
                        # TODO: Start buffering or suspend outgoing events
                        # while RP is connected, because apparently Elk stops
                        # responding to non-RP connections
                        #rp_status = int(event.data_str[0:1])
                        # Status 0: Elk RP disconnected (IE also sent, no need
                        # to rescan from RP event)
                        # Status 1: Elk RP connected, M1XEP poll reply, this
                        # occurs in response to commands sent while RP is
                        # connected
                        # Status 2: Elk RP connected, M1XEP poll reply during
                        # M1XEP powerup/reboot, this happens during RP
                        # disconnect sequence before it's completely disco'd
                        _LOGGER.debug('elk_queue_process - Event.EVENT_INSTALLER_ELKRP')
                        continue
                    elif event.type == Event.EVENT_ETHERNET_TEST:
                        # Consume ethernet test events,
                        # but we don't do anything with them
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ETHERNET_TEST')
                        continue
                    elif event.type == Event.EVENT_ALARM_MEMORY:
                        # TODO: Implement
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ALARM_MEMORY')
                        continue
                    elif event.type == Event.EVENT_TROUBLE_STATUS_REPLY:
                        # TODO: Implement
                        _LOGGER.debug('elk_queue_process - Event.EVENT_TROUBLE_STATUS_REPLY')
                        continue
                    elif event.type == Event.EVENT_ENTRY_EXIT_TIMER:
                        # Entry/Exit timer started or updated
                        areanumber = int(event.data[0])
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ENTRY_EXIT_TIMER')
                        self.AREAS[areanumber].unpack_event_entry_exit_timer(event)
                        continue
                    elif event.type == Event.EVENT_USER_CODE_ENTERED:
                        # User code entered
                        _LOGGER.debug('elk_queue_process - Event.EVENT_USER_CODE_ENTERED')
                        keypadnumber = int(event.data_str[15:17])
                        self.KEYPADS[keypadnumber].unpack_event_user_code_entered(event)
                        continue
                    elif event.type == Event.EVENT_TASK_UPDATE:
                        # Task activated
                        tasknumber = int(event.data_str[:3])
                        _LOGGER.debug('elk_queue_process - Event.EVENT_TASK_UPDATE')
                        self.TASKS[tasknumber].unpack_event_task_update(event)
                        continue
                    elif event.type == Event.EVENT_OUTPUT_UPDATE:
                        # Output changed state
                        outputnumber = int(event.data_str[:3])
                        _LOGGER.debug('elk_queue_process - Event.EVENT_OUTPUT_UPDATE')
                        self.OUTPUTS[outputnumber].unpack_event_output_update(event)
                        continue
                    elif event.type == Event.EVENT_ZONE_UPDATE:
                        # Zone changed state
                        zonenumber = int(event.data_str[:3])
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ZONE_UPDATE')
                        self.ZONES[zonenumber].unpack_event_zone_update(event)
                        continue
                    elif event.type == Event.EVENT_KEYPAD_STATUS_REPORT:
                        # Keypad changed state
                        keypadnumber = int(event.data_str[:2])
                        _LOGGER.debug('elk_queue_process - Event.EVENT_KEYPAD_STATUS_REPORT')
                        self.KEYPADS[keypadnumber].unpack_event_keypad_status_report(event)
                        continue
                    elif event.type == Event.EVENT_ARMING_STATUS_REPORT:
                        # Alarm status changed
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ARMING_STATUS_REPORT')
                        for node_index in range(1, 9):
                            self.AREAS[node_index].unpack_event_arming_status_report(event)
                        continue
                    elif event.type == Event.EVENT_ALARM_ZONE_REPORT:
                        # Alarm zone changed
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ALARM_ZONE_REPORT')
                        for node_index in range(1, 209):
                            self.ZONES[node_index].unpack_event_alarm_zone(event)
                        continue
                    elif event.type == Event.EVENT_TEMP_REQUEST_REPLY:
                        # Temp sensor update
                        _LOGGER.debug('elk_queue_process - Event.EVENT_TEMP_REQUEST_REPLY')
                        group = int(event.data[0])
                        node_index = int(event.data_str[1:3])
                        if node_index == 0:
                            continue
                        if group == 0:
                            # Group 0 temp probe (Zone 1-16)
                            self.ZONES[node_index].unpack_event_temp_request_reply(event)
                            continue
                        elif group == 1:
                            # Group 1 temp probe (Keypad)
                            self.KEYPADS[node_index].unpack_event_temp_request_reply(event)
                            continue
                        elif group == 2:
                            # Group 2 temp probe (Thermostat)
                            self.THERMOSTATS[node_index].unpack_event_temp_request_reply(event)
                            continue
                        continue
                    elif event.type == Event.EVENT_THERMOSTAT_DATA_REPLY:
                        # Thermostat update
                        _LOGGER.debug('elk_queue_process - Event.EVENT_THERMOSTAT_DATA_REPLY')
                        node_index = int(event.data_str[0:2])
                        if node_index > 0:
                            self.THERMOSTATS[node_index].unpack_event_thermostat_data_reply(event)
                        continue
                    elif event.type == Event.EVENT_PLC_CHANGE_UPDATE:
                        # PLC Change Update
                        _LOGGER.debug('elk_queue_process - Event.EVENT_PLC_CHANGE_UPDATE')
                        house = ord(event.data_str[0]) - ord('A')
                        device = int(event.data_str[1:3])
                        offset = (house * 16) + device
                        self.X10[offset].unpack_event_plc_change_update(event)
                        continue
                    elif event.type == Event.EVENT_VERSION_REPLY:
                        # Version reply
                        _LOGGER.debug('elk_queue_process - Event.EVENT_VERSION_REPLY')
                        self.unpack_event_version_reply(event)
                        continue

    def get_version(self):
        """Get Elk and (if available) M1XEP version information."""
        return self._elk_versions

    def unpack_event_version_reply(self, event):
        """Unpack Event.EVENT_VERSION_REPLY.

        Event data format: UUMMLLuummllD[36]
        UUMMLL: M1 version, UU=Most, MM=Middle, LL=Least significant
        uummll: M1XEP version, UU=Most, MM=Middle, LL=Least significant
        D[36]: 36 zeros for future use
        """
        version_elk = event.data_str[:2] + '.' + event.data_str[2:4]\
        + '.' + event.data_str[4:6]
        version_m1xep = event.data_str[6:8] + '.' + event.data_str[8:10]\
        + '.' + event.data_str[10:12]
        self._elk_versions = {'Elk M1' : version_elk, 'M1XEP' : version_m1xep}

    def scan_zones(self):
        """Scan all Zones and their information."""
        # Get Zone status report
        event = Event()
        event.type = Event.EVENT_ZONE_STATUS
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_ZONE_STATUS_REPORT)
        if reply:
            _LOGGER.debug('scan_zones : got Event.EVENT_ZONE_STATUS_REPORT')
            for node_index in range(1, 209):
                self.ZONES[node_index].unpack_event_zone_status_report(reply)
        else:
            # Some kind of error, should never happen.
            return False
        # Get Zone alarm type configuration
        event = Event()
        event.type = Event.EVENT_ALARM_ZONE
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_ALARM_ZONE_REPORT)
        if reply:
            _LOGGER.debug('scan_zones : got Event.EVENT_ALARM_ZONE_REPORT')
            for node_index in range(1, 209):
                self.ZONES[node_index].unpack_event_alarm_zone(reply)
        # Get Zone definition type configuration
        event = Event()
        event.type = Event.EVENT_ZONE_DEFINITION
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_ZONE_DEFINITION_REPLY)
        if reply:
            _LOGGER.debug('scan_zones : got Event.EVENT_ZONE_DEFINITION_REPLY')
            for node_index in range(1, 209):
                self.ZONES[node_index].unpack_event_zone_definition(reply)
        # Get Zone area (partition) assignments
        event = Event()
        event.type = Event.EVENT_ZONE_PARTITION
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_ZONE_PARTITION_REPORT)
        if reply:
            _LOGGER.debug('scan_zones : got Event.EVENT_ZONE_PARTITION_REPORT')
            for node_index in range(1, 209):
                self.ZONES[node_index].unpack_event_zone_partition(reply)
        # Check for Analog zones
        node_index = 1
        while node_index < 209:
            if (self.ZONES[node_index].definition
                    == Zone.DEFINITION_ANALOG_ZONE)\
            and (self.ZONES[node_index].included is True):
                event = Event()
                event.type = Event.EVENT_ZONE_VOLTAGE
                event.data_str = format(node_index, '03')
                self.elk_event_send(event)
                reply = self.elk_event_scan(Event.EVENT_ZONE_VOLTAGE_REPLY)
                if reply:
                    _LOGGER.debug('scan_zones : got Event.EVENT_ZONE_VOLTAGE_REPLY')
                    zonenumber = int(reply.data_str[0:3])
                    self.ZONES[zonenumber].unpack_event_zone_voltage(reply)
            node_index += 1
        # Check for Temperature zones on Zones 1-16
        for node_index in range(1, 17):
            if (self.ZONES[node_index].definition == Zone.DEFINITION_TEMPERATURE)\
            and (self.ZONES[node_index].included is True):
                event = Event()
                event.type = Event.EVENT_TEMP_REQUEST
                event.data_str = '0' + format(node_index, '02')
                self.elk_event_send(event)
                # Request Group 0 (Zone) temperature
                reply = self.elk_event_scan(Event.EVENT_TEMP_REQUEST_REPLY,
                                            '0' + format(node_index, '02'))
                if reply:
                    _LOGGER.debug('scan_zones : got Event.EVENT_TEMP_REQUEST_REPLY')
                    group = int(reply.data[0])
                    number = int(event.data_str[1:3])
                    _LOGGER.debug('scan_zones : temperature group={} number={} rawtemp={}'\
                                  .format(group, number, reply.data_str[3:6]))
                    if (group == 0) and (number == node_index):
                        self.ZONES[number].unpack_event_temp_request_reply(reply)
                    else:
                        _LOGGER.debug('scan_zones : error reading temperature, ' + str(number))
        # Get Zone descriptions
        node_index = 1
        while (node_index) and (node_index < 209):
            if self.ZONES[node_index].included is True:
                node_index = self.get_description(Event.DESCRIPTION_ZONE_NAME,
                                                  node_index)
            else:
                node_index = node_index + 1

    def scan_outputs(self):
        """Scan all Outputs and their information."""
        event = Event()
        event.type = Event.EVENT_OUTPUT_STATUS
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_OUTPUT_STATUS_REPORT)
        if reply:
            _LOGGER.debug('scan_outputs : got Event.EVENT_OUTPUT_STATUS_REPORT')
            for node_index in range(1, 209):
                self.OUTPUTS[node_index].unpack_event_output_status_report(reply)
        else:
            return False

        node_index = 1
        while (node_index) and (node_index < 209):
            if self.OUTPUTS[node_index].included is True:
                node_index = self.get_description(
                    Event.DESCRIPTION_OUTPUT_NAME, node_index)
            else:
                node_index = node_index + 1

    def scan_areas(self):
        """Scan all Areas and their information."""
        event = Event()
        event.type = Event.EVENT_ARMING_STATUS
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_ARMING_STATUS_REPORT)
        if reply:
            _LOGGER.debug('scan_areas : got Event.EVENT_ARMING_STATUS_REPORT')
            for node_index in range(1, 9):
                self.AREAS[node_index].unpack_event_arming_status_report(reply)
        else:
            return False

        node_index = 1
        while (node_index) and (node_index < 9):
            if self.AREAS[node_index].included is True:
                node_index = self.get_description(Event.DESCRIPTION_AREA_NAME,
                                                  node_index)
            else:
                node_index = node_index + 1

    def scan_keypads(self):
        """Scan all Keypads and their information."""
        event = Event()
        event.type = Event.EVENT_KEYPAD_AREA
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_KEYPAD_AREA_REPLY)
        if reply:
            _LOGGER.debug('scan_keypads : got Event.EVENT_KEYPAD_AREA_REPLY')
            for node_index in range(1, 17):
                self.KEYPADS[node_index].unpack_event_keypad_area_reply(reply)
                if self.KEYPADS[node_index].included is True:
                    event = Event()
                    event.type = Event.EVENT_KEYPAD_STATUS
                    event.data_str = format(node_index, '02')
                    self.elk_event_send(event)
                    report = self.elk_event_scan(Event.EVENT_KEYPAD_STATUS_REPORT)
                    if report:
                        _LOGGER.debug('scan_keypads : got Event.EVENT_KEYPAD_STATUS_REPORT')
                        keypadnumber = int(report.data_str[:2])
                        self.KEYPADS[keypadnumber].unpack_event_keypad_status_report(report)
                    event = Event()
                    event.type = Event.EVENT_TEMP_REQUEST
                    event.data_str = '1' + format(node_index, '02')
                    self.elk_event_send(event)
                    temp_reply = self.elk_event_scan(Event.EVENT_TEMP_REQUEST_REPLY,\
                                                     '1' + format(node_index, '02'))
                    if temp_reply:
                        _LOGGER.debug('scan_keypads : got Event.EVENT_TEMP_REQUEST_REPLY')
                        group = int(temp_reply.data[0])
                        number = int(temp_reply.data_str[1:3])
                        _LOGGER.debug('scan_keypads : temperature group={} number={} rawtemp={}'\
                                      .format(group, number, temp_reply.data_str[3:6]))
                        if (group == 1) and (number == node_index):
                            self.KEYPADS[keypadnumber].unpack_event_temp_request_reply(temp_reply)
                        else:
                            _LOGGER.debug('scan_keypads : error reading temperature, '\
                                          + str(number))
            node_index = 1
            while (node_index) and (node_index < 17):
                if self.KEYPADS[node_index].included is True:
                    node_index = self.get_description(Event.DESCRIPTION_KEYPAD_NAME, node_index)
                else:
                    node_index = node_index +1
        else:
            return False

    def scan_thermostats(self):
        """Scan all Thermostats and their information."""
        for node_index in range(1, 17):
            if self.THERMOSTATS[node_index].included is True:
                event = Event()
                event.type = Event.EVENT_THERMOSTAT_DATA_REQUEST
                event.data_str = format(node_index, '02')
                self.elk_event_send(event)
                reply = self.elk_event_scan(Event.EVENT_THERMOSTAT_DATA_REPLY,
                                            format(node_index, '02'))
                if reply:
                    _LOGGER.debug('scan_thermostats : got Event.EVENT_THERMOSTAT_DATA_REPLY')
                    self.THERMOSTATS[node_index].unpack_event_thermostat_data_reply(reply)
        node_index = 1
        while (node_index) and (node_index < 17):
            if self.THERMOSTATS[node_index].included is True:
                node_index = self.get_description(Event.DESCRIPTION_THERMOSTAT_NAME, node_index)
            else:
                node_index = node_index + 1

    def scan_x10(self):
        """Scan all X10 devices and their information."""
        for node_index_group in range(0, 4):
            # TODO: Skip queries if all devices in block are excluded
            event = Event()
            event.type = Event.EVENT_PLC_STATUS_REQUEST
            event.data_str = format(node_index_group, '01')
            self.elk_event_send(event)
            reply = self.elk_event_scan(Event.EVENT_PLC_STATUS_REPLY,
                                        format(node_index_group, '01'))
            if reply:
                _LOGGER.debug('scan_x10 : got Event.EVENT_PLC_STATUS_REPLY')
                for node_index in range(node_index_group+1, node_index_group+17):
                    self.X10[node_index].unpack_event_plc_status_reply(reply)
        node_index = 1
        while (node_index) and (node_index < 257):
            if self.X10[node_index].included is True:
                node_index = self.get_description(Event.DESCRIPTION_LIGHT_NAME, node_index)
            else:
                node_index = node_index + 1

    def scan_tasks(self):
        """Scan all Tasks and their information."""
        node_index = 1
        while (node_index) and (node_index < 33):
            if self.TASKS[node_index].included is True:
                node_index = self.get_description(Event.DESCRIPTION_TASK_NAME, node_index)
            else:
                node_index = node_index + 1

    def get_description(self, description_type, number):
        """Request string description from Elk.

        If there is nothing set for the requested description,
        the Elk will return the next valid description instead,
        so we must check the returned description and set accordingly.

        description_type: Type of description to request.
        number: Index of description type (i.e. Zone number).
        """
        event = Event()
        event.type = Event.EVENT_DESCRIPTION
        data = format(description_type, '02') + format(number, '03')
        event.data_str = data
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_DESCRIPTION_REPLY)
        if reply:
            _LOGGER.debug('get_description : got Event.EVENT_DESCRIPTION_REPLY')
            reply.dump()
            reply_type = int(reply.data_str[:2])
            replynumber = int(reply.data_str[2:5])
            reply_name = reply.data_str[5:21]
            if replynumber >= number:
                if reply_type == Event.DESCRIPTION_ZONE_NAME:
                    self.ZONES[replynumber].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_OUTPUT_NAME:
                    self.OUTPUTS[replynumber].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_AREA_NAME:
                    self.AREAS[replynumber].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_KEYPAD_NAME:
                    self.KEYPADS[replynumber].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_LIGHT_NAME:
                    self.X10[replynumber].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_TASK_NAME:
                    self.TASKS[replynumber].description = reply_name.strip()
                return replynumber+1
        return False

    def _list_from_ranges(self, data):
        """Converts a list of ranges to a list

        d can be a list of values or single value,
        each value is either a string with a single number (ex: '4'),
        or a hyphenated range (ex: '5-9'). Ex: ['4','5-9'] -> [4,5,6,7,8,9]
        """
        if not isinstance(data, list):
            data = [data]
        result = []
        for ranges in data:
            if '-' in ranges:
                range_start, range_end = ranges.split('-')
                if (range_start.isdigit()) and (range_end.isdigit()):
                    # Regular numeric ranges
                    x10_start, x10_end = int(range_start), int(range_end)
                else:
                    # X10 device ranges, presumably
                    x10 = X10(self)
                    x10_start = x10.housecode_to_int(range_start)
                    x10_end = x10.housecode_to_int(range_end)
                    if (x10_start is None) or (x10_end is None):
                        continue
                result.extend(list(range(x10_start, x10_end + 1)))
            else:
                range_start = int(ranges)
                result.append(range_start)
        return result

class NullHandler(logging.Handler):
    def emit(self, record):
        pass
