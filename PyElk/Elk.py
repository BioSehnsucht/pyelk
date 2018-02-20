"""Implementation of the main PyElk class, which is the interface used to
initiate and control communications with the Elk device.
"""
from collections import deque
import logging
import time
import traceback
import json
import threading

from .Connection import Connection

from .Const import *
from .Node import Node
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
    Event.EVENT_OMNISTAT_DATA_REPLY,
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

class Scanner(object):
    """Scanner class handles rescanning of Elk system on a separate thread."""

    STATE_SCAN_IDLE = 0
    STATE_SCAN_START = 1
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
    STATE_SCAN_VERSION = 20

    SCAN_NEXT = {
        STATE_SCAN_IDLE : STATE_SCAN_START,
        STATE_SCAN_START : STATE_SCAN_ZONES,
        STATE_SCAN_ZONES: STATE_SCAN_OUTPUTS,
        STATE_SCAN_OUTPUTS : STATE_SCAN_AREAS,
        STATE_SCAN_AREAS : STATE_SCAN_KEYPADS,
        STATE_SCAN_KEYPADS : STATE_SCAN_TASKS,
        STATE_SCAN_TASKS : STATE_SCAN_THERMOSTATS,
        STATE_SCAN_THERMOSTATS : STATE_SCAN_X10,
        STATE_SCAN_X10 : STATE_SCAN_USERS,
        STATE_SCAN_USERS : STATE_SCAN_COUNTERS,
        STATE_SCAN_COUNTERS : STATE_SCAN_SETTINGS,
        STATE_SCAN_SETTINGS : STATE_SCAN_VERSION,
        STATE_SCAN_VERSION : STATE_SCAN_IDLE,
        }

    def __init__(self, pyelk):
        self._pyelk = pyelk
        self._stopping = False
        self._state = self.STATE_SCAN_IDLE
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

    @property
    def state(self):
        """Return thread state."""
        return self._state

    def run(self):
        """Thread that handles rescanning of Elk system."""
        while not self._stopping:
            if self._state == self.STATE_SCAN_IDLE:
                _LOGGER.debug('Scanning idle')
                self._pyelk.state = self._pyelk.STATE_RUNNING
                self._event.clear()
                self._event.wait()
            if self._state == self.STATE_SCAN_START:
                _LOGGER.debug('Starting scan')
            elif self._state == self.STATE_SCAN_ZONES:
                _LOGGER.debug('Scanning zones')
                self._pyelk.scan_zones()
            elif self._state == self.STATE_SCAN_OUTPUTS:
                _LOGGER.debug('Scanning outputs')
                self._pyelk.scan_outputs()
            elif self._state == self.STATE_SCAN_AREAS:
                _LOGGER.debug('Scanning areas')
                self._pyelk.scan_areas()
            elif self._state == self.STATE_SCAN_KEYPADS:
                _LOGGER.debug('Scanning keypads')
                self._pyelk.scan_keypads()
            elif self._state == self.STATE_SCAN_TASKS:
                _LOGGER.debug('Scanning tasks')
                self._pyelk.scan_tasks()
            elif self._state == self.STATE_SCAN_THERMOSTATS:
                _LOGGER.debug('Scanning thermostats')
                self._pyelk.scan_thermostats()
            elif self._state == self.STATE_SCAN_X10:
                _LOGGER.debug('Scanning X10')
                self._pyelk.scan_x10()
            elif self._state == self.STATE_SCAN_USERS:
                _LOGGER.debug('Scanning users')
                self._pyelk.scan_users()
            elif self._state == self.STATE_SCAN_COUNTERS:
                _LOGGER.debug('Scanning counters')
                self._pyelk.scan_counters()
            elif self._state == self.STATE_SCAN_SETTINGS:
                _LOGGER.debug('Scanning settings')
                self._pyelk.scan_settings()
            elif self._state == self.STATE_SCAN_VERSION:
                _LOGGER.debug('Scanning version')
                self._pyelk.scan_version()
            self._state = self.SCAN_NEXT[self._state]


class Elk(Node):
    """
    This is the main class that handles interaction with the Elk panel

    |  config['host']: String of the IP address of the ELK-M1XEP,
       or device name of the serial device connected to the Elk panel,
       ex: 'socket://192.168.12.34:2101' or '/dev/ttyUSB0'
    |  config['ratelimit'] [optional]: rate limit for outgoing events (default 10/s)
    |  log: [optional] Log file class from logging module
    """

    STATE_DISCONNECTED = 0
    STATE_CONNECTING = 1
    STATE_RUNNING = 2
    STATE_PAUSED = 3

    STATUS_STR = {
        STATE_DISCONNECTED : 'Disconnected',
        STATE_CONNECTING : 'Connecting',
        STATE_RUNNING : 'Running',
        STATE_PAUSED : 'Paused',
    }

    def __init__(self, config, log=None):
        """Initializes Elk object.

        config: dictionary containing configuration
        usercode: Alarm user code (not currently used, may be removed).
        log: Logger object to use.
        """
        # Let Node initialize common things
        super().__init__('System')
        self._connection = None
        self._status = self.STATE_DISCONNECTED
        self._unpaused_status = None
        self._state_fastload_enabled = True
        self._state_fastload_file = 'PyElk-fastload.json'
        self._events = None
        self._reconnect_thread = None
        self._config = config
        self._queue_incoming_elk_events = deque(maxlen=1000)
        self._queue_outgoing_elk_events = None
        #self._queue_exported_events = deque(maxlen=1000)
        self._rescan_thread = Scanner(self)
        self._update_in_progress = False
        self._elk_versions = None
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

        # Perform fast load of previous state before returning
        if 'fastload' in self._config:
            self._state_fastload_enabled = self._config['fastload']
        if 'fastload_file' in self._config:
            self._state_fastload_file = self._config['fastload_file']
        if self._state_fastload_enabled:
            self.state_load()

    @property
    def connected(self):
        if self._status == self.STATE_RUNNING or self._status == self.STATE_PAUSED:
                return True
        return False

    def connect(self):
        """Attempt to connect to Elk."""
        try:
            ratelimit = 10
            if 'ratelimit' in self._config:
                ratelimit = self._config['ratelimit']
            self._status = self.STATE_CONNECTING
            self._connection = Connection()
            self._connection.connect(self, self._config['host'], ratelimit)

        except ValueError as exception_error:
            self._status = self.STATE_DISCONNECTED
            try:
                self.log.error(exception_error.message)
            except AttributeError:
                self.log.error(exception_error.args[0])

        if self._connection.connected:
            self._status = self.STATE_RUNNING
            self._rescan()

    def stop(self):
        """Stop PyElk and disconnect from Elk."""
        self._status = self.STATE_DISCONNECTED
        self._connection = None
        return

    def description_pretty(self, prefix='Elk M1G System'):
        """Elk system description."""
        return prefix

    def promoted_callback(self, node, data=None):
        """Handles callbacks that are promoted upwards due
           to not having a callback registered."""
        if (data is None) and (node is not None):
            self.callback_trigger(node)
        else:
            self.callback_trigger(data)
        return

    @property
    def _rescan_in_progress(self):
        """Get state of rescan thread."""
        if self._rescan_thread.state == Scanner.STATE_SCAN_IDLE:
            return False
        else:
            return True

    def state_save(self):
        """Save current state to fast load state file."""
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

        state_data = {}

        for device_class_num in range_order:
            device_class = range_order[device_class_num]
            state_data[device_class] = []
            for node_index in range(0, max_range[device_class]):
                data = False
                if device_class == 'zone':
                    data = self.ZONES[node_index].state_save()
                elif device_class == 'output':
                    data = self.OUTPUTS[node_index].state_save()
                elif device_class == 'area':
                    data = self.AREAS[node_index].state_save()
                elif device_class == 'keypad':
                    data = self.KEYPADS[node_index].state_save()
                elif device_class == 'thermostat':
                    data = self.THERMOSTATS[node_index].state_save()
                elif device_class == 'x10':
                    data = self.X10[node_index].state_save()
                elif device_class == 'task':
                    data = self.TASKS[node_index].state_save()
                elif device_class == 'user':
                    data = self.USERS[node_index].state_save()
                elif device_class == 'counter':
                    data = self.COUNTERS[node_index].state_save()
                elif device_class == 'setting':
                    data = self.SETTINGS[node_index].state_save()
                if data:
                    state_data[device_class].append(data)

        with open(self._state_fastload_file, 'w') as f:
            json.dump(state_data, f)
        return

    def state_load(self):
        """Load state from fast load state file."""

        state_data = {}
        _LOGGER.debug('Performing fastload')
        try:
            with open(self._state_fastload_file, 'r') as f:
                state_data = json.load(f)
        except ValueError:
            _LOGGER.debug('Failed to load fast load file - value error')
            return
        except FileNotFoundError:
            _LOGGER.debug('Failed to load fast load file - file not found')
            return
        else:
            for device_class in state_data:
                for node_index in range(0,len(state_data[device_class])):
                    data = state_data[device_class][node_index]
                    if device_class == 'zone':
                        self.ZONES[node_index].state_load(data)
                    elif device_class == 'output':
                        self.OUTPUTS[node_index].state_load(data)
                    elif device_class == 'area':
                        self.AREAS[node_index].state_load(data)
                    elif device_class == 'keypad':
                        self.KEYPADS[node_index].state_load(data)
                    elif device_class == 'thermostat':
                        self.THERMOSTATS[node_index].state_load(data)
                    elif device_class == 'x10':
                        self.X10[node_index].state_load(data)
                    elif device_class == 'task':
                        self.TASKS[node_index].state_load(data)
                    elif device_class == 'user':
                        self.USERS[node_index].state_load(data)
                    elif device_class == 'counter':
                        self.COUNTERS[node_index].state_load(data)
                    elif device_class == 'setting':
                        self.SETTINGS[node_index].state_load(data)
        return

    def _rescan(self):
        """Rescan all things.

        Normally called on startup, and if the panel has left
        programming mode (via Keypad or ElkRP).
        """
        if self._rescan_in_progress is True:
            return
        self._rescan_thread.resume()

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
        if self._connection._elkrp_connected:
            _LOGGER.debug('Not queuing event due to active ElkRP: {}\n'.format(repr(event_str)))
        else:
            _LOGGER.debug('Queuing: {}\n'.format(repr(event_str)))
            self._queue_outgoing_elk_events.append(event)
            self._connection._connection_output.resume()

    def elk_event_send_actual(self, event):
        """Send an Elk event to the Elk.

        event: Event to send to Elk.
        """
        event_str = event.to_string()
        _LOGGER.debug('Sending: {}\n'.format(repr(event_str)))
        self._connection._connection_protocol.write_line(event_str)

    def elk_event_enqueue(self, data):
        """Add event to the incoming event deque.

        data: Event to place on the deque.
        """
        event = Event()
        event.parse(data)
        self._queue_incoming_elk_events.append(event)
        # Remove any pending retries if this is an expected reply
        for retry_event in list(self._queue_outgoing_elk_events):
            if len(retry_event.expect) > 0:
                match_len = len(retry_event.expect)
                data_str = event.data_str[0:match_len]
                if data_str == retry_event.expect:
                    self._queue_outgoing_elk_events.remove(retry_event)
            break;
        self.update()

    def elk_event_scan(self, event_type, data_match=None, timeout=10,
                       output_scan=False, reverse=False):
        """Scan the incoming event deque for specified event type.

        event_type: Event type or types to look for.
        data_match: If set (either single string or list of strings),
        in addition to matching the event_type, we will also compare
        the event data (up to len(data_match)) and only return an
        event if at least one of the data_match matches the event.
        timeout: Time to wait for new events if none already in deque,
        default is 10 seconds.
        output_scan: If true, we scan the output queue instead
        reverse: If true, scan the queue in reverse order
        """
        sleep_interval = 0.1
        scan_queue = None
        if output_scan:
            scan_queue = self._queue_outgoing_elk_events
        else:
            scan_queue = self._queue_incoming_elk_events
        reverse_flag = 1
        if reverse:
            reverse_flag = -1
        endtime = time.time() + timeout
        if not isinstance(event_type, list):
            event_type = [event_type]
        event = None
        if (data_match is not None) and (not isinstance(data_match, list)):
            data_match = [data_match]
        first_try = True
        while time.time() <= endtime:
            # If not our first loop, sleep for a moment
            if first_try:
                first_try = False
            else:
                time.sleep(sleep_interval)
            # Iterate the queue for events
            for elem in list(scan_queue)[::reverse_flag]:
                if elem.type in event_type:
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
                        if not output_scan:
                            self._queue_incoming_elk_events.remove(elem)
                        return event
            # For output scan, no point waiting for the future
            if output_scan:
                return False

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
                            self._connection._elkrp_connected = False
                            if self._unpaused_status is not None:
                                self._status = self._unpaused_status
                                self._unpaused_status = None
                        # Status 1: Elk RP connected, M1XEP poll reply, this
                        # occurs in response to commands sent while RP is
                        # connected
                        elif rp_status == 1:
                            self._connection._elkrp_connected = True
                            if self._status is not self.STATE_PAUSED:
                                self._unpaused_status = self._status
                                self._status = self.STATE_PAUSED
                        # Status 2: Elk RP connected, M1XEP poll reply during
                        # M1XEP powerup/reboot, this happens during RP
                        # disconnect sequence before it's completely disco'd
                        elif rp_status == 2:
                            self._connection._elkrp_connected = True
                            if self._status is not self.STATE_PAUSED:
                                self._unpaused_status = self._status
                                self._status = self.STATE_PAUSED
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
                        node_index = areanumber - 1
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ENTRY_EXIT_TIMER')
                        self.AREAS[node_index].unpack_event_entry_exit_timer(event)
                        continue
                    elif event.type == Event.EVENT_USER_CODE_ENTERED:
                        # User code entered
                        _LOGGER.debug('elk_queue_process - Event.EVENT_USER_CODE_ENTERED')
                        keypadnumber = int(event.data_str[15:17])
                        node_index = keypadnumber - 1
                        self.KEYPADS[node_index].unpack_event_user_code_entered(event)
                        continue
                    elif event.type == Event.EVENT_TASK_UPDATE:
                        # Task activated
                        tasknumber = int(event.data_str[:3])
                        node_index = tasknumber - 1
                        _LOGGER.debug('elk_queue_process - Event.EVENT_TASK_UPDATE')
                        self.TASKS[node_index].unpack_event_task_update(event)
                        continue
                    elif event.type == Event.EVENT_OUTPUT_UPDATE:
                        # Output changed state
                        outputnumber = int(event.data_str[:3])
                        node_index = outputnumber - 1
                        _LOGGER.debug('elk_queue_process - Event.EVENT_OUTPUT_UPDATE')
                        self.OUTPUTS[node_index].unpack_event_output_update(event)
                        continue
                    elif event.type == Event.EVENT_ZONE_UPDATE:
                        # Zone changed state
                        zonenumber = int(event.data_str[:3])
                        node_index = zonenumber - 1
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ZONE_UPDATE')
                        self.ZONES[node_index].unpack_event_zone_update(event)
                        continue
                    elif event.type == Event.EVENT_KEYPAD_STATUS_REPORT:
                        # Keypad changed state
                        keypadnumber = int(event.data_str[:2])
                        node_index = keypadnumber - 1
                        _LOGGER.debug('elk_queue_process - Event.EVENT_KEYPAD_STATUS_REPORT')
                        self.KEYPADS[node_index].unpack_event_keypad_status_report(event)
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
                        self.state_save()
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
                    elif event.type == Event.EVENT_OMNISTAT_DATA_REPLY:
                        # Omnistat 2 data reply
                        _LOGGER.debug('elk_queue_process - got Event.EVENT_OMNISTAT_DATA_REPLY')
                        for node_index in range(0, THERMOSTAT_MAX_COUNT):
                            self.THERMOSTATS[node_index].unpack_event_omnistat_data_reply(event)
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
        self._updated_at = event.time
        self._callback()

    def scan_version(self):
        """Scan Elk system version."""
        event = Event()
        event.type = Event.EVENT_VERSION
        self.elk_event_send(event)

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
                self.THERMOSTATS[node_index].request_temp()
                self.THERMOSTATS[node_index].detect_omni()
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
                    self.ZONES[node_index].callback_trigger()
                elif reply_type == Event.DESCRIPTION_OUTPUT_NAME:
                    self.OUTPUTS[node_index].description = reply_name.strip()
                    self.OUTPUTS[node_index].callback_trigger()
                elif reply_type == Event.DESCRIPTION_AREA_NAME:
                    self.AREAS[node_index].description = reply_name.strip()
                    self.AREAS[node_index].callback_trigger()
                elif reply_type == Event.DESCRIPTION_KEYPAD_NAME:
                    self.KEYPADS[node_index].description = reply_name.strip()
                    self.KEYPADS[node_index].callback_trigger()
                elif reply_type == Event.DESCRIPTION_LIGHT_NAME:
                    self.X10[node_index].description = reply_name.strip()
                    self.X10[node_index].callback_trigger()
                elif reply_type == Event.DESCRIPTION_TASK_NAME:
                    self.TASKS[node_index].description = reply_name.strip()
                    self.TASKS[node_index].callback_trigger()
                elif reply_type == Event.DESCRIPTION_USER_NAME:
                    self.USERS[node_index].description = reply_name.strip()
                    self.USERS[node_index].callback_trigger()
                elif reply_type == Event.DESCRIPTION_COUNTER_NAME:
                    self.COUNTERS[node_index].description = reply_name.strip()
                    self.COUNTERS[node_index].callback_trigger()
                elif reply_type == Event.DESCRIPTION_CUSTOM_SETTING_NAME:
                    self.SETTINGS[node_index].description = reply_name.strip()
                    self.SETTINGS[node_index].callback_trigger()
                elif reply_type == Event.DESCRIPTION_THERMOSTAT_NAME:
                    self.THERMOSTATS[node_index].description = reply_name.strip()
                    self.THERMOSTATS[node_index].callback_trigger()
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
            if (isinstance(ranges, int)):
                ranges = str(ranges)
            num_start = 0
            num_end = 0
            if '-' in ranges:
                split_start, split_end = ranges.split('-')
                if (split_start.isdigit()) and (split_end.isdigit()):
                    # Regular numeric ranges
                    num_start, num_end = int(split_start), int(split_end)
                else:
                    # X10 device ranges, presumably
                    num_start = X10.housecode_to_int(split_start)
                    num_end = X10.housecode_to_int(split_end)
                    if (num_start is None) or (num_end is None):
                        continue
                range_start = num_start - 1
                range_end = num_end - 1
                result.extend(list(range(range_start, range_end + 1)))
            else:
                range_start = None
                num_start = 0
                if ranges.isdigit():
                    num_start = int(ranges)
                else:
                    num_start = X10.housecode_to_int(ranges)
                range_start = num_start - 1
                result.append(num_start)
        return result

class NullHandler(logging.Handler):
    """Null logging handler."""
    def emit(self, record):
        """pass all."""
        pass
