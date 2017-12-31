"""Elk Counter."""
from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Const import *
from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class Counter(Node):
    """Represents a Counter in the Elk."""
    def __init__(self, pyelk=None, number=None):
        """Initializes Counter object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super().__init__('Counter', pyelk, number)
        # Initialize Output specific things
        # (none currently)

    def description_pretty(self, prefix='Counter '):
        """Area description, as text string (auto-generated if not set)."""
        return super().description_pretty(prefix)

    def get_value(self):
        """Get counter value.

        Using EVENT_COUNTER_READ

        Event data format: NN
        NN: Counter number
        """
        event = Event()
        event.type = Event.EVENT_COUNTER_READ
        event.data_str = format(self._number, '02')
        self._pyelk.elk_event_send(event)

    def set_value(self, value):
        """Set counter value.

        Using EVENT_COUNTER_WRITE.

        Event data format: NNDDDDD
        NN: Counter number
        DDDDD: 16 bit counter value, ASCII decimal '00000' .. '65535'
        """
        event = Event()
        event.type = Event.EVENT_COUNTER_WRITE
        event.data_str = format(self._number, '02') + format(value, '05')
        self._pyelk.elk_event_send(event)

    def unpack_event_counter_reply(self, event):
        """Unpack EVENT_COUNTER_REPLY.

        Event data format: NNDDDDD
        NN: Counter number
        DDDDD: 16 bit counter value, ASCII decimal '00000' .. '65535'
        """
        data = int(event.data_str[2:8])
        if self._status == data:
            return
        self._status = data
        self._updated_at = event.time
        self._callback()
