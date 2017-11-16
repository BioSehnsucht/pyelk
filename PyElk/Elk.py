"""Implementation of the main PyElk class, which is the interface used to
initiate and control communications with the Elk device.
"""
from collections import deque
import logging
import time
import traceback
import threading
import serial
import serial.threaded

from .Const import *
from .Area import Area
from .Counter import Counter
from .Event import Event
from .Keypad import Keypad
from .Output import Output
from .Setting import Setting
from .Task import Task
from .Thermostat import Thermostat
from .User import User
from .X10 import X10
from .Zone import Zone


_LOGGER = logging.getLogger(__name__)

# Events automatically handled under normal circumstances
# by elk_process_event
EVENT_LIST_AUTO_PROCESS = [
    Event.EVENT_ALARM_ZONE_REPORT,
    Event.EVENT_ALARM_MEMORY,
    Event.EVENT_ARMING_STATUS_REPORT,
    Event.EVENT_COUNTER_REPLY,
    Event.EVENT_ENTRY_EXIT_TIMER,
    Event.EVENT_ETHERNET_TEST,
    Event.EVENT_INSTALLER_ELKRP,
    Event.EVENT_INSTALLER_EXIT,
    Event.EVENT_KEYPAD_AREA_REPLY,
    Event.EVENT_KEYPAD_STATUS_REPORT,
    Event.EVENT_OUTPUT_STATUS_REPORT,
    Event.EVENT_OUTPUT_UPDATE,
    Event.EVENT_PLC_CHANGE_UPDATE,
    Event.EVENT_RTC_REPLY,
    Event.EVENT_PLC_STATUS_REPLY,
    Event.EVENT_TASK_UPDATE,
    Event.EVENT_TEMP_REQUEST_REPLY,
    Event.EVENT_THERMOSTAT_DATA_REPLY,
    Event.EVENT_TROUBLE_STATUS_REPLY,
    Event.EVENT_USER_CODE_ENTERED,
    Event.EVENT_VALUE_READ_REPLY,
    Event.EVENT_VERSION_REPLY,
    Event.EVENT_ZONE_DEFINITION_REPLY,
    Event.EVENT_ZONE_PARTITION_REPORT,
    Event.EVENT_ZONE_STATUS_REPORT,
    Event.EVENT_ZONE_UPDATE,
    ]

# Events specifically NOT handled automatically by elk_process_event
# while rescan is in progress
EVENT_LIST_RESCAN_BLACKLIST = [
    Event.EVENT_ZONE_DEFINITION_REPLY,
    Event.EVENT_ZONE_STATUS_REPORT,
    ]


class SerialInputHandler(serial.threaded.LineReader):
    """LaneHandler implementation for serial.threaded."""

    def set_pyelk(self, pyelk):
        """Sets the pyelk instance to use."""
        self._pyelk = pyelk

    # Implement Protocol class functions for Threaded Serial
    def connection_made(self, transport):
        """Called when connection is made."""
        _LOGGER.debug('Calling super connection_made')
        super(SerialInputHandler, self).connection_made(transport)
        _LOGGER.debug('Connected')

    def handle_line(self, line):
        """Validate event and add to incoming buffer."""
        self._pyelk.elk_event_enqueue(line)
        _LOGGER.debug('handle_line: ' + line)

    def connection_lost(self, exc):
        """Connection was lost."""
        _LOGGER.debug('Lost connection')
        self._pyelk._connection_output.stop()
        if exc:
            traceback.print_exc(exc)

class SerialOutputHandler(object):
    """SerialOutputHandler handles outputting events to serial.threaded via deque."""

    def set_pyelk(self, pyelk):
        """Sets the pyelk instance to use."""
        self._pyelk = pyelk

    def __init__(self, ratelimit=1):
        """Setup output handler."""
        self._pyelk = None
        self._interval = 1.0 / ratelimit
        self._stopping = False
        self._event = threading.Event()
        thread = threading.Thread(target=self.run, args=())
        thread.start()

    def stop(self):
        """Stop thread."""
        self._stopping = True

    def pause(self):
        """Pause thread."""
        self._event.clear()

    def resume(self):
        """Resume thread."""
        self._event.set()

    def run(self):
        """Thread that handles outputting queued events to the Elk."""
        while not self._stopping:
            self._event.wait()
            self._event.clear()
            _LOGGER.debug('woke up send queue : ' + str(len(self._pyelk._queue_outgoing_elk_events)))
            for event in list(self._pyelk._queue_outgoing_elk_events):
                self._pyelk.elk_event_send_actual(event)
                self._pyelk._queue_outgoing_elk_events.remove(event)
                time.sleep(self._interval)

class Elk(object):
    """
    This is the main class that handles interaction with the Elk panel

    |  config['host']: String of the IP address of the ELK-M1XEP,
       or device name of the serial device connected to the Elk panel,
       ex: 'socket://192.168.12.34:2101' or '/dev/ttyUSB0'
    |  config['ratelimit'] [optional]: rate limit for outgoing events (default 10/s)
    |  log: [optional] Log file class from logging module

    :ivar log: Logger used by the class and its children.
    """

    STATE_DISCONNECTED = 0
    STATE_RUNNING = 1
    STATE_SCAN_AREAS = 10
    STATE_SCAN_COUNTERS = 11
    STATE_SCAN_KEYPADS = 12
    STATE_SCAN_OUTPUTS = 13
    STATE_SCAN_SETTINGS = 14
    STATE_SCAN_TASKS = 15
    STATE_SCAN_THERMOSTATS = 16
    STATE_SCAN_USERS = 17
    STATE_SCAN_X10 = 18
    STATE_SCAN_ZONES = 19

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
        self._queue_outgoing_elk_events = deque(maxlen=1000)
        self._queue_exported_events = deque(maxlen=1000)
        self._rescan_in_progress = False
        self._update_in_progress = False
        self._elkrp_connected = False
        self._elk_versions = None
        self._connection_protocol = None
        self._connection_thread = None
        self._connection_output = None
        self.AREAS = []
        self.COUNTERS = []
        self.KEYPADS = []
        self.OUTPUTS = []
        self.SETTINGS = []
        self.TASKS = []
        self.THERMOSTATS = []
        self.USERS = []
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
            'zone': ZONE_MAX_COUNT,
            'output' : OUTPUT_MAX_COUNT,
            'area' : AREA_MAX_COUNT,
            'keypad' : KEYPAD_MAX_COUNT,
            'thermostat' : THERMOSTAT_MAX_COUNT,
            'user' : USER_MAX_COUNT,
            'x10' : X10_MAX_COUNT,
            'task' : TASK_MAX_COUNT,
            'counter' : COUNTER_MAX_COUNT,
            'setting' : SETTING_MAX_COUNT,
            }

        range_order = {
            0 : 'zone',
            1 : 'output',
            2 : 'area',
            3 : 'keypad',
            4 : 'thermostat',
            5 : 'x10',
            6 : 'task',
            7 : 'user',
            8 : 'counter',
            9 : 'setting',
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
                include_range = range(0, max_range[device_class])
            if exclude_range is None:
                exclude_range = []
            self.log.debug('PyElk config - ' + device_class + ' include range: %s', include_range)
            self.log.debug('PyElk config - ' + device_class + ' exclude range: %s', exclude_range)
            for device_num in range(0, max_range[device_class]):
                # Create device
                if device_class == 'zone':
                    device = Zone(self, device_num)
                elif device_class == 'output':
                    device = Output(self, device_num)
                elif device_class == 'area':
                    device = Area(self, device_num)
                elif device_class == 'keypad':
                    device = Keypad(self, device_num)
                elif device_class == 'thermostat':
                    device = Thermostat(self, device_num)
                elif device_class == 'x10':
                    device = X10(self, device_num)
                elif device_class == 'task':
                    device = Task(self, device_num)
                elif device_class == 'user':
                    device = User(self, device_num)
                elif device_class == 'counter':
                    device = Counter(self, device_num)
                elif device_class == 'setting':
                    device = Setting(self, device_num)
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
                elif device_class == 'user':
                    self.USERS.append(device)
                elif device_class == 'counter':
                    self.COUNTERS.append(device)
                elif device_class == 'setting':
                    self.SETTINGS.append(device)
        try:
            ratelimit = 10
            if 'ratelimit' in self._config:
                ratelimit = self._config['ratelimit']
            self.connect(self._config['host'], ratelimit)

        except ValueError as exception_error:
            try:
                self.log.error(exception_error.message)
            except AttributeError:
                self.log.error(exception_error.args[0])

        if self.connected:
            self._rescan()

    def __del__(self):
        """Shutdown communications."""
        if self._connection_thread is not None:
            self._connection_output.stop()
            self._connection_output.close()
            self._connection_thread.close()

    @property
    def connected(self):
        """True if connected to Elk panel."""
        if self._connection_thread:
            return self._connection_thread.alive and self._connection_thread.serial.is_open
        return False

    def connect(self, address, ratelimit):
        """Connect to the Elk panel.

        address: Host to connect to in either
        "socket://IP.Add.re.ss:Port" or "/dev/ttyUSB0" format.
        ratelimit: rate limit for outgoing events
        """
        self._connection = serial.serial_for_url(address, timeout=1)
        self._connection_thread = serial.threaded.ReaderThread(self._connection, SerialInputHandler)
        self._connection_thread.start()
        self._connection_transport, self._connection_protocol = self._connection_thread.connect()
        self._connection_protocol.set_pyelk(self)
        self._connection_output = SerialOutputHandler(ratelimit)
        self._connection_output.set_pyelk(self)
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
        self._state = self.STATE_SCAN_USERS
        self.scan_users()
        self._state = self.STATE_SCAN_COUNTERS
        self.scan_counters()
        self._state = self.STATE_SCAN_SETTINGS
        self.scan_settings()
        self._rescan_in_progress = False
        self._state = self.STATE_RUNNING

    def exported_event_enqueue(self, data):
        """Add event to the exported event deque.

        Not actually used yet, may get removed.

        data: Event to place on the deque.
        """
        self._queue_exported_events.append(data)

    def elk_event_send(self, event):
        """Queue an Elk event to the Elk.

        event: Event to send to Elk.
        """
        event_str = event.to_string()
        if self._elkrp_connected:
            _LOGGER.debug('Discarding due to ElkRP: {}\n'.format(repr(event_str)))
        else:
            _LOGGER.debug('Queuing: {}\n'.format(repr(event_str)))
            self._queue_outgoing_elk_events.append(event)
            self._connection_output.resume()

    def elk_event_send_actual(self, event):
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
        if (not isinstance('list', data_match)) and (data_match is not None):
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
        """Process any available incoming events."""
        self.elk_queue_process()

    def elk_queue_process(self):
        """Process the incoming event deque."""
        if self._update_in_progress:
            return
        self._update_in_progress = True
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
                        # but we don't do anything with them except prevent sending events
                        rp_status = int(event.data_str[0:1])
                        # Status 0: Elk RP disconnected (IE also sent, no need
                        # to rescan from RP event)
                        if rp_status == 0:
                            self._queue_outgoing_elk_events.clear()
                            self._elkrp_connected = False
                        # Status 1: Elk RP connected, M1XEP poll reply, this
                        # occurs in response to commands sent while RP is
                        # connected
                        elif rp_status == 1:
                            self._elkrp_connected = True
                        # Status 2: Elk RP connected, M1XEP poll reply during
                        # M1XEP powerup/reboot, this happens during RP
                        # disconnect sequence before it's completely disco'd
                        elif rp_status == 2:
                            self._elkrp_connected = True
                        _LOGGER.debug('elk_queue_process - Event.EVENT_INSTALLER_ELKRP')
                        continue
                    elif event.type == Event.EVENT_ETHERNET_TEST:
                        # Consume ethernet test events,
                        # but we don't do anything with them
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ETHERNET_TEST')
                        continue
                    elif event.type == Event.EVENT_ALARM_MEMORY:
                        # Alarm Memory update
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ALARM_MEMORY')
                        for node_index in range(0, AREA_MAX_COUNT):
                            self.AREAS[node_index].unpack_event_alarm_memory(event)
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
                        for node_index in range(0, AREA_MAX_COUNT):
                            self.AREAS[node_index].unpack_event_arming_status_report(event)
                        continue
                    elif event.type == Event.EVENT_ALARM_ZONE_REPORT:
                        # Alarm zone changed
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ALARM_ZONE_REPORT')
                        for node_index in range(0, ZONE_MAX_COUNT):
                            self.ZONES[node_index].unpack_event_alarm_zone(event)
                        continue
                    elif event.type == Event.EVENT_TEMP_REQUEST_REPLY:
                        # Temp sensor update
                        _LOGGER.debug('elk_queue_process - Event.EVENT_TEMP_REQUEST_REPLY')
                        group = int(event.data[0])
                        node_index = int(event.data_str[1:3])-1
                        if node_index < 0:
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
                        node_index = int(event.data_str[0:2])-1
                        if node_index >= 0:
                            self.THERMOSTATS[node_index].unpack_event_thermostat_data_reply(event)
                        continue
                    elif event.type == Event.EVENT_PLC_CHANGE_UPDATE:
                        # PLC Change Update
                        _LOGGER.debug('elk_queue_process - Event.EVENT_PLC_CHANGE_UPDATE')
                        house_code = event.data_str[0]
                        device_code = int(event.data_str[1:3])
                        offset = X10.housecode_to_index(hc=house_code+device_code)
                        self.X10[offset].unpack_event_plc_change_update(event)
                        continue
                    elif event.type == Event.EVENT_VERSION_REPLY:
                        # Version reply
                        _LOGGER.debug('elk_queue_process - Event.EVENT_VERSION_REPLY')
                        self.unpack_event_version_reply(event)
                        continue
                    elif event.type == Event.EVENT_COUNTER_REPLY:
                        # Counter reply
                        _LOGGER.debug('elk_queue_process - Event.EVENT_COUNTER_REPLY')
                        node_index = int(event.data_str[0:2])-1
                        if node_index >= 0:
                            self.COUNTERS[node_index].unpack_event_counter_reply(event)
                        continue
                    elif event.type == Event.EVENT_VALUE_READ_REPLY:
                        # Setting reply
                        _LOGGER.debug('elk_queue_process - Event.EVENT_VALUE_READ_REPLY')
                        node_index = int(event.data_str[0:2])-1
                        _LOGGER.debug('node_index : ' + str(node_index))
                        if node_index < 0:
                            # Reply all
                            for node_index in range(0, SETTING_MAX_COUNT):
                                self.SETTINGS[node_index].unpack_event_value_read_reply(event)
                        else:
                            # Reply one
                            self.SETTINGS[node_index].unpack_event_value_read_reply(event)
                        continue
                    elif event.type == Event.EVENT_RTC_REPLY:
                        # Real Time Clock data reply
                        # We don't do anything with this currently
                        _LOGGER.debug('elk_queue_process - Event.EVENT_RTC_REPLY')
                        continue
                    elif event.type == Event.EVENT_OUTPUT_STATUS_REPORT:
                        # Output Status Report
                        _LOGGER.debug('elk_queue_process - Event.EVENT_OUTPUT_STATUS_REPORT')
                        for node_index in range(0, OUTPUT_MAX_COUNT):
                            self.OUTPUTS[node_index].unpack_event_output_status_report(event)
                        continue
                    elif event.type == Event.EVENT_KEYPAD_AREA_REPLY:
                        # Keypad Area Reply
                        _LOGGER.debug('elk_queue_process - Event.EVENT_KEYPAD_AREA_REPLY')
                        for node_index in range(0, KEYPAD_MAX_COUNT):
                            self.KEYPADS[node_index].unpack_event_keypad_area_reply(event)
                        continue
                    elif event.type == Event.EVENT_PLC_STATUS_REPLY:
                        # PLC Status Reply
                        _LOGGER.debug('elk_queue_process - Event.EVENT_PLC_STATUS_REPLY')
                        group_base = int(event.data_str[0])
                        for node_index in range(group_base, group_base+64):
                            self.X10[node_index].unpack_event_plc_status_reply(event)
                        continue
                    elif event.type == Event.EVENT_ZONE_PARTITION_REPORT:
                        # Zone Partition Report
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ZONE_PARTITION_REPORT')
                        for node_index in range(0, ZONE_MAX_COUNT):
                            self.ZONES[node_index].unpack_event_zone_partition(event)
                        continue
                    elif event.type == Event.EVENT_ZONE_DEFINITION_REPLY:
                        # Zone Definition Reply
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ZONE_DEFINITION_REPLY')
                        for node_index in range(0, ZONE_MAX_COUNT):
                            self.ZONES[node_index].unpack_event_zone_definition(event)
                        continue
                    elif event.type == Event.EVENT_ZONE_STATUS_REPORT:
                        # Zone Status Report
                        _LOGGER.debug('elk_queue_process - got Event.EVENT_ZONE_STATUS_REPORT')
                        for node_index in range(0, ZONE_MAX_COUNT):
                            self.ZONES[node_index].unpack_event_zone_status_report(event)
                        continue
        self._update_in_progress = False

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
        reply = self.elk_event_scan(Event.EVENT_ZONE_STATUS_REPORT, timeout=30)
        if reply:
            _LOGGER.debug('scan_zones : got Event.EVENT_ZONE_STATUS_REPORT')
            for node_index in range(0, ZONE_MAX_COUNT):
                self.ZONES[node_index].unpack_event_zone_status_report(reply)
        else:
            _LOGGER.debug('scan_zones : timeout waiting for Event.EVENT_ZONE_STATUS_REPORT')
        # Get Zone definition type configuration
        event = Event()
        event.type = Event.EVENT_ZONE_DEFINITION
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_ZONE_DEFINITION_REPLY)
        if reply:
            _LOGGER.debug('scan_zones : got Event.EVENT_ZONE_DEFINITION_REPLY')
            for node_index in range(0, ZONE_MAX_COUNT):
                self.ZONES[node_index].unpack_event_zone_definition(reply)
        # Get Zone alarm type configuration
        event = Event()
        event.type = Event.EVENT_ALARM_ZONE
        self.elk_event_send(event)
        # Get Zone area (partition) assignments
        event = Event()
        event.type = Event.EVENT_ZONE_PARTITION
        self.elk_event_send(event)
        # Check for Analog zones
        for node_index in range(0, ZONE_MAX_COUNT):
            if (self.ZONES[node_index].definition
                    == Zone.DEFINITION_ANALOG_ZONE)\
            and (self.ZONES[node_index].included is True):
                event = Event()
                event.type = Event.EVENT_ZONE_VOLTAGE
                event.data_str = format(self.ZONES[node_index].number, '03')
                self.elk_event_send(event)
        # Check for Temperature zones on Zones 1-16
        for node_index in range(0, ZONE_MAX_TEMP_COUNT):
            if (self.ZONES[node_index].definition == Zone.DEFINITION_TEMPERATURE)\
            and (self.ZONES[node_index].included is True):
                event = Event()
                event.type = Event.EVENT_TEMP_REQUEST
                event.data_str = '0' + format(self.ZONES[node_index].number, '02')
                self.elk_event_send(event)
        # Get Zone descriptions
        desc_index = 1
        while (desc_index) and (desc_index <= ZONE_MAX_COUNT):
            if self.ZONES[desc_index-1].included is True:
                desc_index = self.get_description(Event.DESCRIPTION_ZONE_NAME,
                                                  desc_index)
            else:
                desc_index = desc_index + 1

    def scan_outputs(self):
        """Scan all Outputs and their information."""
        event = Event()
        event.type = Event.EVENT_OUTPUT_STATUS
        self.elk_event_send(event)

        desc_index = 1
        while (desc_index) and (desc_index <= OUTPUT_MAX_COUNT):
            if self.OUTPUTS[desc_index-1].included is True:
                desc_index = self.get_description(
                    Event.DESCRIPTION_OUTPUT_NAME, desc_index)
            else:
                desc_index = desc_index + 1

    def scan_areas(self):
        """Scan all Areas and their information."""
        event = Event()
        event.type = Event.EVENT_ARMING_STATUS
        self.elk_event_send(event)

        desc_index = 1
        while (desc_index) and (desc_index <= AREA_MAX_COUNT):
            if self.AREAS[desc_index-1].included is True:
                desc_index = self.get_description(Event.DESCRIPTION_AREA_NAME,
                                                  desc_index)
            else:
                desc_index = desc_index + 1

    def scan_keypads(self):
        """Scan all Keypads and their information."""
        event = Event()
        event.type = Event.EVENT_KEYPAD_AREA
        self.elk_event_send(event)
        for node_index in range(0, KEYPAD_MAX_COUNT):
            if self.KEYPADS[node_index].included is True:
                event = Event()
                event.type = Event.EVENT_KEYPAD_STATUS
                event.data_str = format(self.KEYPADS[node_index].number, '02')
                self.elk_event_send(event)
                event = Event()
                event.type = Event.EVENT_TEMP_REQUEST
                event.data_str = '1' + format(self.KEYPADS[node_index].number, '02')
                self.elk_event_send(event)
        desc_index = 1
        while (desc_index) and (desc_index <= KEYPAD_MAX_COUNT):
            if self.KEYPADS[desc_index-1].included is True:
                desc_index = self.get_description(Event.DESCRIPTION_KEYPAD_NAME, desc_index)
            else:
                desc_index = desc_index + 1

    def scan_thermostats(self):
        """Scan all Thermostats and their information."""
        for node_index in range(0, THERMOSTAT_MAX_COUNT):
            if self.THERMOSTATS[node_index].included is True:
                event = Event()
                event.type = Event.EVENT_THERMOSTAT_DATA_REQUEST
                event.data_str = format(self.THERMOSTATS[node_index].number, '02')
                self.elk_event_send(event)
        desc_index = 1
        while (desc_index) and (desc_index <= THERMOSTAT_MAX_COUNT):
            if self.THERMOSTATS[desc_index-1].included is True:
                desc_index = self.get_description(Event.DESCRIPTION_THERMOSTAT_NAME, desc_index)
            else:
                desc_index = desc_index + 1

    def scan_x10(self):
        """Scan all X10 devices and their information."""
        for node_index_group in range(0, 4):
            group_base = node_index_group * 64
            group_excluded = True
            for node_index in range(group_base, group_base+64):
                if self.X10[node_index].included is True:
                    group_excluded = False
            if group_excluded is True:
                continue
            event = Event()
            event.type = Event.EVENT_PLC_STATUS_REQUEST
            event.data_str = format(node_index_group, '01')
            self.elk_event_send(event)

        desc_index = 1
        while (desc_index) and (desc_index <= X10_MAX_COUNT):
            if self.X10[desc_index-1].included is True:
                desc_index = self.get_description(Event.DESCRIPTION_LIGHT_NAME, desc_index)
            else:
                desc_index = desc_index + 1

    def scan_tasks(self):
        """Scan all Tasks and their information."""
        desc_index = 1
        while (desc_index) and (desc_index <= TASK_MAX_COUNT):
            if self.TASKS[desc_index-1].included is True:
                desc_index = self.get_description(Event.DESCRIPTION_TASK_NAME, desc_index)
            else:
                desc_index = desc_index + 1

    def scan_users(self):
        """Scan all Users and their information."""
        desc_index = 1
        while (desc_index) and (desc_index <= USER_MAX_COUNT):
            if self.USERS[desc_index-1].included is True:
                desc_index = self.get_description(Event.DESCRIPTION_USER_NAME, desc_index)
            else:
                desc_index = desc_index + 1

    def scan_counters(self):
        """Scan all Counters and their information."""
        for node_index in range(0, COUNTER_MAX_COUNT):
            if self.COUNTERS[node_index].included is True:
                event = Event()
                event.type = Event.EVENT_COUNTER_READ
                event.data_str = format(self.COUNTERS[node_index].number, '02')
                self.elk_event_send(event)
        desc_index = 1
        while (desc_index) and (desc_index <= COUNTER_MAX_COUNT):
            if self.COUNTERS[desc_index-1].included is True:
                desc_index = self.get_description(Event.DESCRIPTION_COUNTER_NAME, desc_index)
            else:
                desc_index = desc_index + 1

    def scan_settings(self):
        """Scan all Settings and their information."""
        event = Event()
        event.type = Event.EVENT_VALUE_READ_ALL
        self.elk_event_send(event)
        desc_index = 1
        while (desc_index) and (desc_index <= SETTING_MAX_COUNT):
            if self.SETTINGS[desc_index-1].included is True:
                desc_index = self.get_description(Event.DESCRIPTION_CUSTOM_SETTING_NAME, desc_index)
            else:
                desc_index = desc_index + 1

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
            reply_number = int(reply.data_str[2:5])
            reply_name = reply.data_str[5:21]
            if reply_number >= number:
                node_index = reply_number - 1
                if reply_type == Event.DESCRIPTION_ZONE_NAME:
                    self.ZONES[node_index].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_OUTPUT_NAME:
                    self.OUTPUTS[node_index].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_AREA_NAME:
                    self.AREAS[node_index].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_KEYPAD_NAME:
                    self.KEYPADS[node_index].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_LIGHT_NAME:
                    self.X10[node_index].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_TASK_NAME:
                    self.TASKS[node_index].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_USER_NAME:
                    self.USERS[node_index].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_COUNTER_NAME:
                    self.COUNTERS[node_index].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_CUSTOM_SETTING_NAME:
                    self.SETTINGS[node_index].description = reply_name.strip()
                elif reply_type == Event.DESCRIPTION_THERMOSTAT_NAME:
                    self.THERMOSTATS[node_index].description = reply_name.strip()
                return reply_number+1
        return False

    @staticmethod
    def _list_from_ranges(data):
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
                    range_start = X10.housecode_to_int(range_start)
                    range_end = X10.housecode_to_int(range_end)
                    if (range_start is None) or (range_end is None):
                        continue
                range_start = range_start - 1
                range_end = range_end - 1
                result.extend(list(range(x10_start, x10_end + 1)))
            else:
                range_start = None
                if ranges.is_digit():
                    range_start = int(ranges)
                else:
                    range_start = X10.housecode_to_int(ranges)
                range_start = range_start - 1
                result.append(range_start)
        return result

class NullHandler(logging.Handler):
    """Null logging handler."""
    def emit(self, record):
        """pass all."""
        pass
