from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class Output(Node):
    STATUS_OFF = 0
    STATUS_ON = 1

    STATUS_STR = {
        STATUS_OFF : 'Off',
        STATUS_ON : 'On'
    }

    def __init__(self, pyelk = None, number = None):
        """Initializes Output object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super(Output, self).__init__(pyelk, number)
        # Initialize Output specific things
        # (none currently)

    def description(self):
        """Output description, as text string (auto-generated if not set)."""
        return super(Output, self).description('Output ')

    def turn_on(self, duration = 0):
        """Turn on output, optionally for a specified duration.

        duration: Duration in seconds for output to turn on, 0 is inf.
        """
        event = Event()
        event._type = Event.EVENT_OUTPUT_ON
        if duration < 0:
            duration = 0
        elif duration > 65535:
            duration = 65535
        event._data_str = format(self._number,'03') + format(duration,'05')
        self._pyelk.elk_event_send(event)

    def turn_off(self):
        """Turn off output."""
        event = Event()
        event._type = Event.EVENT_OUTPUT_OFF
        event._data_str = format(self._number,'03')
        self._pyelk.elk_event_send(event)

    def toggle(self):
        """Toggle output state."""
        event = Event()
        event._type = Event.EVENT_OUTPUT_TOGGLE
        event._data_str = format(self._number,'03')
        self._pyelk.elk_event_send(event)


    def dump(self):
        """Dump debugging data, to be removed."""
        _LOGGER.debug('Output Status: {}\n'.format(repr(self.status())))
        _LOGGER.debug('Output Description: {}\n'.format(repr(self.description())))

    def unpack_event_output_status_report(self, event):
        """Unpack EVENT_OUTPUT_STATUS_REPORT.

        Event data format: D[208]
        D[208]: 208 byte ASCII array of output status,
        '0' is off, '1' is on
        """
        data = event.data_dehex()[self._number-1]
        if (self._status == data):
            return
        self._status = data
        self._updated_at = event._time
        self._callback()

    def unpack_event_output_update(self, event):
        """Unpack EVENT_OUTPUT_UPDATE.

        Event data format: ZZZS
        ZZZ: Output number, ASCII decimal
        S: Output state, '0' is off, '1' is on
        """
        data = int(event.data_dehex()[3])
        if (self._status == data):
            return
        self._status = data
        self._updated_at = event._time
        self._callback()
