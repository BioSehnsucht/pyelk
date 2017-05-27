from collections import namedtuple
from collections import deque
import logging
import serial
import serial.threaded
import time
import traceback

_LOGGER = logging.getLogger(__name__)

from .Event import Event
from .Zone import Zone
from .Output import Output
from .Area import Area
from .Keypad import Keypad

"""Events automatically handled under normal circumstances"""
event_auto_map = [
    Event.EVENT_INSTALLER_EXIT,
    Event.EVENT_ALARM_MEMORY,
    Event.EVENT_ENTRY_EXIT_TIMER,
    Event.EVENT_USER_CODE_ENTERED,
    Event.EVENT_TASK_UPDATE,
    Event.EVENT_OUTPUT_UPDATE,
    Event.EVENT_ZONE_UPDATE,
    Event.EVENT_KEYPAD_STATUS_REPORT,
    Event.EVENT_ETHERNET_TEST,
    Event.EVENT_ARMING_STATUS_REPORT,
    Event.EVENT_ALARM_ZONE_REPORT
    ]

"""Events specifically NOT handled automatically while rescan in progress"""
event_scan_map = [
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
    Event.EVENT_ZONE_VOLTAGE_REPLY
    ]


class LineHandler(serial.threaded.LineReader):
    _pyelk = None

    def set_pyelk(self, pyelk):
        self._pyelk = pyelk

    # Implement Protocol class functions for Threaded Serial
    def connection_made(self, transport):
        _LOGGER.debug('Calling super connection_made')
        super(LineHandler, self).connection_made(transport)
        _LOGGER.debug('Connected')

    def handle_line(self, data):
        # Validate event and add to incoming buffer
        self._pyelk.elk_event_enqueue(data)
        _LOGGER.debug('handle_line: ' + data)
        self._pyelk.update()

    def connection_lost(self, exc):
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

    EXPORTED_EVENT_NONE = 0 
    EXPORTED_EVENT_RESCAN = 1 # Rescan performed, many things may have changed
    EXPORTED_EVENT_ZONE_STATUS = 2 # Change in zone status (open/closed, violated, etc)
    EXPORTED_EVENT_OUTPUT_STATUS = 3 # Change in output status (on/off, etc)
    EXPORTED_EVENT_ALARM_STATUS = 4 # Change in alarm status (arm/disarm, alarming, etc)
    EXPORTED_EVENT_KEYPAD_STATUS = 5 # Change in keypad status (keypress, illumination, user code entered, etc)


    ZONES = []
    OUTPUTS = []
    AREAS = []
    KEYPADS = []

    _rescan_in_progress = False

    _elk_versions = None

    _connectionProtocol = None
    _connectionThread = None

    def __init__(self, address, usercode, log=None):
        self._events = None
        self._reconnect_thread = None
        self._usercode = usercode
        self._queue_incoming_elk_events = deque(maxlen=1000)
        self._queue_exported_events = deque(maxlen=1000)

        # Using 0..N+1 and putting None in 0 so we aren't constantly converting between 0 and 1 based as often...
        # May change back to 0..N at a later date 
        for z in range(0,209):
            if z == 0:
                zone = None
            else:
                zone = Zone(self)
                zone._number = z
            self.ZONES.append(zone)

        for o in range(0,209):
            if o == 0:
                output = None
            else:
                output = Output(self)
                output._number = o
            self.OUTPUTS.append(output)

        for a in range(0,9):
            if a == 0:
                area = None
            else:
                area = Area(self)
                area._number = a
            self.AREAS.append(area)

        for k in range(0,17):
            if k == 0:
                keypad = None
            else:
                keypad = Keypad(self)
                keypad._number = k
            self.KEYPADS.append(keypad)

        if log is None:
            self.log = logging.getLogger(__name__)
            self.log.addHandler(NullHandler())
        else:
            self.log = log

        try:
            self.connect(address)

        except ValueError as e:
            try:
                self.log.error(e.message)
            except AttributeError:
                self.log.error(e.args[0])

        if (self.connected):
            self._rescan()

    def __del__(self):
        self._connectionThread.close()

    @property
    def connected(self):
        if (self._connectionThread):
            return (self._connectionThread.alive and self._connectionThread.serial.is_open)
        else:
            return False

    def connect(self, address):
        self._connection = serial.serial_for_url(address, timeout=1)
        self._connectionThread = serial.threaded.ReaderThread(self._connection, LineHandler) # or ReaderThread(self._connection, self... ?)
        self._connectionThread.start()
        self._connectionTransport, self._connectionProtocol = self._connectionThread.connect()
        self._connectionProtocol.set_pyelk(self)
        _LOGGER.debug('ReaderThread created')

    def _rescan(self):

        self._rescan_in_progress = True
        self.scan_zones()
        self.scan_outputs()
        self.scan_areas()
        self.scan_keypads()
        self._rescan_in_progress = False

    def exported_event_enqueue(self, data):
        self._queue_exported_events.append(data)        
    
    def elk_event_send(self, event):
        event_str = event.to_string()
        _LOGGER.debug('Sending: {}\n'.format(repr(event_str)))
        self._connectionProtocol.write_line(event_str)

    def elk_event_enqueue(self, data):
        event = Event()
        event.parse(data)
        self._queue_incoming_elk_events.append(event)
        self.update()

    def elk_event_scan(self, event_type, timeout = 10):
        endtime = time.time() + timeout
        event = None
        while (time.time() <= endtime):
            for elem in list(self._queue_incoming_elk_events):
                if (elem._type == event_type):
                    event = elem
                    self._queue_incoming_elk_events.remove(elem)
                    return event
        else:
            _LOGGER.debug('elk_event_scan : timeout')
            return False

    def update(self):
        self.elk_queue_process()

    def elk_queue_process(self):
        _LOGGER.debug('elk_queue_process - checking events')
        for event in list(self._queue_incoming_elk_events):
            """Remove stale events over 120 seconds old, normally shouldn't happen"""
            if (event.age() > 120):
                self._queue_incoming_elk_events.remove(event)
                _LOGGER.error('elk_queue_process - removing stale event: ' + str(repr(event._type)))
            elif (event._type in event_auto_map):
                """Event is one we handle automatically"""
                if (self._rescan_in_progress) and (event._type in event_scan_map):
                    """Skip for now, scanning may consume the event instead"""
                    _LOGGER.debug('elk_queue_process - rescan in progress, skipping: ' + str(repr(event._type)))
                    continue
                else:
                    """Process event"""
                    self._queue_incoming_elk_events.remove(event)
                    if (event._type == Event.EVENT_INSTALLER_EXIT):
                        """Initiate a rescan if the Elk just left 
                        installer mode and break out of the loop"""
                        _LOGGER.debug('elk_queue_process - Event.EVENT_INSTALLER_EXIT')
                        self._rescan()
                        return
                    elif (event._type == Event.EVENT_ETHERNET_TEST):
                        """Consume ethernet test packets, but we don't do anything with them"""
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ETHERNET_TEST')
                        continue
                    elif (event._type == Event.EVENT_ALARM_MEMORY):
                        """TODO: Implement"""
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ALARM_MEMORY')
                        continue
                    elif (event._type == Event.EVENT_ENTRY_EXIT_TIMER):
                        """Entry/Exit timer started or updated"""
                        area_number = int(event._data[0])
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ENTRY_EXIT_TIMER')
                        self.AREAS[area_number].unpack_event_entry_exit_timer(event)
                        continue
                    elif (event._type == Event.EVENT_USER_CODE_ENTERED):
                        """TODO: Implement"""
                        _LOGGER.debug('elk_queue_process - Event.EVENT_USER_CODE_ENTERED')
                        continue
                    elif (event._type == Event.EVENT_TASK_UPDATE):
                        """TODO: Implement"""
                        _LOGGER.debug('elk_queue_process - Event.EVENT_TASK_UPDATE')
                        continue
                    elif (event._type == Event.EVENT_OUTPUT_UPDATE):
                        """Output changed state"""
                        output_number = int(event._data_str[:3])
                        _LOGGER.debug('elk_queue_process - Event.EVENT_OUTPUT_UPDATE')
                        self.OUTPUTS[output_number].unpack_event_output_update(event)
                        continue
                    elif (event._type == Event.EVENT_ZONE_UPDATE):
                        """Zone changed state"""
                        zone_number = int(event._data_str[:3])
                        _LOGGER.debug('elk_queue_process - Event.EVENT_ZONE_UPDATE')
                        self.ZONES[zone_number].unpack_event_zone_update(event)
                        continue
                    elif (event._type == Event.EVENT_KEYPAD_STATUS_REPORT):
                        """Keypad changed state"""
                        keypad_number = int(event._data_str[:2])
                        _LOGGER.debug('elk_queue_process - Event.EVENT_KEYPAD_STATUS_REPORT')
                        self.KEYPADS[keypad_number].unpack_event_keypad_status_report(event)
                        continue
                    elif (event._type == Event.EVENT_ARMING_STATUS_REPORT):
                        """Alarm status changed"""
                        for a in range (1,9):
                            self.AREAS[a].unpack_event_arming_status_report(event)
                        continue
                    elif (event._type == Event.EVENT_ALARM_ZONE_REPORT):
                        """Alarm zone changed"""
                        for z in range (1,209):
                            self.ZONES[z].unpack_event_alarm_zone(event)
                        continue



    def get_version(self):
        event = Event()
        event._type = Event.EVENT_VERSION
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_VERSION_REPLY)
        if (reply):
            version_elk = reply._data_str[:2] + '.' + reply._data_str[2:4] + '.' + reply._data_str[4:6]
            version_m1xep = reply._data_str[6:8] + '.' + reply._data_str[8:10] + '.' + reply._data_str[10:12]
            self._elk_versions = {'Elk M1' : version_elk, 'M1XEP' : version_m1xep}
            return self._elk_versions
        else:
            return False

    def scan_zones(self):
        event = Event()
        event._type = Event.EVENT_ZONE_STATUS
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_ZONE_STATUS_REPORT)
        if (reply):
            _LOGGER.debug('scan_zones : got Event.EVENT_ZONE_STATUS_REPORT')
            for z in range(1,209):
                self.ZONES[z].unpack_event_zone_status_report(reply)
        else:
            return False

        event = Event()
        event._type = Event.EVENT_ALARM_ZONE
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_ALARM_ZONE_REPORT)
        if (reply):
            _LOGGER.debug('scan_zones : got Event.EVENT_ALARM_ZONE_REPORT')
            for z in range(1,209):
                self.ZONES[z].unpack_event_alarm_zone(reply)

        event = Event()
        event._type = Event.EVENT_ZONE_DEFINITION
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_ZONE_DEFINITION_REPLY)
        if (reply):
            _LOGGER.debug('scan_zones : got Event.EVENT_ZONE_DEFINITION_REPLY')
            for z in range(1,209):
                self.ZONES[z].unpack_event_zone_definition(reply)

        event = Event()
        event._type = Event.EVENT_ZONE_PARTITION
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_ZONE_PARTITION_REPORT)
        if (reply):
            _LOGGER.debug('scan_zones : got Event.EVENT_ZONE_PARTITION_REPORT')
            for z in range (1,209):
                self.ZONES[z].unpack_event_zone_partition(reply)

        z = 1
        while z < 209:
            if (self.ZONES[z]._definition == Zone.DEFINITION_ANALOG_ZONE):
                event = Event()
                event._type = Event.EVENT_ZONE_VOLTAGE
                event._data_str = format(z,'03')
                self.elk_event_send(event)
                reply = self.elk_event_scan(Event.EVENT_ZONE_VOLTAGE_REPLY)
                if (reply):
                    _LOGGER.debug('scan_zones : got Event.EVENT_ZONE_VOLTAGE_REPLY')
                    zone_number = int(reply._data_str[0:2])
                    self.ZONES[zone_number].unpack_event_zone_voltage(reply)
            z += 1

        z = 1
        while z < 209:
            z = self.get_description(Event.DESCRIPTION_ZONE_NAME,z)

    def scan_outputs(self):
        event = Event()
        event._type = Event.EVENT_OUTPUT_STATUS
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_OUTPUT_STATUS_REPORT)
        if (reply):
            _LOGGER.debug('scan_outputs : got Event.EVENT_OUTPUT_STATUS_REPORT')
            for o in range(1,209):
                self.OUTPUTS[o].unpack_event_output_status_report(reply)
        else:
            return False

        o = 1
        while o < 209:
            o = self.get_description(Event.DESCRIPTION_OUTPUT_NAME,o)

    def scan_areas(self):
        event = Event()
        event._type = Event.EVENT_ARMING_STATUS
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_ARMING_STATUS_REPORT)
        if (reply):
            _LOGGER.debug('scan_areas : got Event.EVENT_OUTPUT_STATUS_REPORT')
            for a in range (1,9):
                self.AREAS[a].unpack_event_arming_status_report(reply)
        else:
            return False

        a = 1
        while a < 9:
            a = self.get_description(Event.DESCRIPTION_AREA_NAME,a)

    def scan_keypads(self):
        event = Event()
        event._type = Event.EVENT_KEYPAD_AREA
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_KEYPAD_AREA_REPLY)
        if (reply):
            _LOGGER.debug('scan_keypads : got Event.EVENT_OUTPUT_STATUS_REPORT')
            for k in range (1,17):
                self.KEYPADS[k].unpack_event_keypad_area_reply(reply)
                event = Event()
                event._type = Event.EVENT_KEYPAD_STATUS
                event._data_str = format(k,'02')
                self.elk_event_send(event)                
                report = self.elk_event_scan(Event.EVENT_KEYPAD_STATUS_REPORT)
                if (report):
                    _LOGGER.debug('scan_keypads : got Event.EVENT_KEYPAD_STATUS_REPORT')
                    keypad_number = int(report._data_str[:2])
                    self.KEYPADS[keypad_number].unpack_event_keypad_status_report(report)
        else:
            return False



    def get_description(self, description_type, number):
        event = Event()
        event._type = Event.EVENT_DESCRIPTION
        data = format(description_type,'02') + format(number,'03')
        event._data_str = data
        self.elk_event_send(event)
        reply = self.elk_event_scan(Event.EVENT_DESCRIPTION_REPLY)
        if (reply):
            _LOGGER.debug('get_description : got Event.EVENT_DESCRIPTION_REPLY')
            reply_type = int(reply._data_str[:2])
            reply_number = int(reply._data_str[2:5])
            reply_name = reply._data_str[5:21]
            if (reply_number >= number):
                if (reply_type == Event.DESCRIPTION_ZONE_NAME):
                    self.ZONES[reply_number]._description = reply_name.strip()
                elif (reply_type == Event.DESCRIPTION_OUTPUT_NAME):
                    self.OUTPUTS[reply_number]._description = reply_name.strip()
                elif (reply_type == Event.DESCRIPTION_AREA_NAME):
                    self.AREAS[reply_number]._description = reply_name.strip()
                elif (reply_type == Event.DESCRIPTION_KEYPAD_NAME):
                    self.KEYPADS[reply_number]._description = reply_name.strip()
                return (reply_number+1)
            
        return 255
