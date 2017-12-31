"""Elk Output."""
from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Const import *
from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class Output(Node):
    """Represents an Output in the Elk."""

    STATUS_OFF = 0
    STATUS_ON = 1

    STATUS_STR = {
        STATUS_OFF : 'Off',
        STATUS_ON : 'On'
    }

    def __init__(self, pyelk=None, number=None):
        """Initializes Output object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super().__init__('Output', pyelk, number)
        # Initialize Output specific things
        # (none currently)

    def description_pretty(self, prefix='Output '):
        """Output description, as text string (auto-generated if not set)."""
        return super().description_pretty(prefix)

    def turn_on(self, duration=0):
        """Turn on output, optionally for a specified duration.

        duration: Duration in seconds for output to turn on, 0 is inf.

        Using EVENT_OUTPUT_ON.

        Event data format: DDDTTTTT
        DDD: Output to turn on, '001' to '208' (ASCII decimal)
        TTTTT: Duration in seconds to turn on, '00000' to '65535' (ASCII decimal)
        """
        event = Event()
        event.type = Event.EVENT_OUTPUT_ON
        if duration < 0:
            duration = 0
        elif duration > 65535:
            duration = 65535
        event.data_str = format(self._number, '03') + format(duration, '05')
        self._pyelk.elk_event_send(event)

    def turn_off(self):
        """Turn off output.

        Using EVENT_OUTPUT_OFF.

        Event data format: DDD
        DDD: Output to turn off, '001' to '208' (ASCII decimal)
        """
        event = Event()
        event.type = Event.EVENT_OUTPUT_OFF
        event.data_str = format(self._number, '03')
        self._pyelk.elk_event_send(event)

    def toggle(self):
        """Toggle output state.

        Using EVENT_OUTPUT_TOGGLE.

        Event data format: DDD
        DDD: Output to toggle, '001' to '208' (ASCII decimal)
        """
        event = Event()
        event.type = Event.EVENT_OUTPUT_TOGGLE
        event.data_str = format(self._number, '03')
        self._pyelk.elk_event_send(event)


    def dump(self):
        """Dump debugging data, to be removed."""
        _LOGGER.debug('Output Status: {}\n'.format(repr(self.status_pretty())))
        _LOGGER.debug('Output Description: {}\n'.format(repr(self.description_pretty())))

    def unpack_event_output_status_report(self, event):
        """Unpack EVENT_OUTPUT_STATUS_REPORT.

        Event data format: D[208]
        D[208]: 208 byte ASCII array of output status,
        '0' is off, '1' is on
        """
        data = event.data_dehex()[self._index]
        if self._status == data:
            return
        self._status = data
        self._updated_at = event.time
        self._callback()

    def unpack_event_output_update(self, event):
        """Unpack EVENT_OUTPUT_UPDATE.

        Event data format: ZZZS
        ZZZ: Output number, ASCII decimal
        S: Output state, '0' is off, '1' is on
        """
        data = int(event.data_dehex()[3])
        if self._status == data:
            return
        self._status = data
        self._updated_at = event.time
        self._callback()
