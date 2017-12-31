"""Elk Setting."""
from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Const import *
from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class Setting(Node):
    """Represents a Setting in the Elk."""

    FORMAT_NUMBER = 0
    FORMAT_TIMER = 1
    FORMAT_TIME_OF_DAY = 2

    FORMAT_STR = {
        FORMAT_NUMBER : 'Number',
        FORMAT_TIMER : 'Timer',
        FORMAT_TIME_OF_DAY : 'Time of Day',
    }

    def __init__(self, pyelk=None, number=None):
        """Initializes Value object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super().__init__('Setting', pyelk, number)
        # Initialize Output specific things
        self._format = self.FORMAT_NUMBER

    def description_pretty(self, prefix='Custom Setting '):
        """Area description, as text string (auto-generated if not set)."""
        return super().description_pretty(prefix)

    @property
    def data_format(self):
        """Returns the data format of this custom setting."""
        return self._format

    @property
    def data_format_pretty(self):
        """Returns the data format of this custom setting as descriptive string."""
        return self.FORMAT_STR[self._format]

    def get_value(self):
        """Get custom setting value.

        Using EVENT_VALUE_READ

        Event data format: NN
        NN: Custom setting number
        """
        event = Event()
        event.type = Event.EVENT_VALUE_READ
        event.data_str = format(self._number, '02')
        self._pyelk.elk_event_send(event)

    def set_value(self, value):
        """Set custom setting value.

        Using EVENT_VALUE_WRITE.

        Event data format: NNDDDDD
        NN: Custom setting number
        DDDDD: 16 bit setting value, ASCII decimal '00000' .. '65535',
               unless format is FORMAT_TIME_OF_DAY (2), in which case it
               is packed
        """
        raw_value = None
        if self._format == self.FORMAT_NUMBER or self._format == self.FORMAT_TIMER:
            raw_value = value
        elif self._format == self.FORMAT_TIME_OF_DAY:
            import datetime
            import dateutil.parser as parser
            tod = None
            if isinstance(value, datetime):
                tod = value
            else:
                tod = parser.parse(value)
            tod_hour = tod.hour
            tod_minute = tod.minute
            raw_value = int(format(tod_hour, '02x') + format(tod_minute, '02x'), 16)
        event = Event()
        event.type = Event.EVENT_VALUE_WRITE
        event.data_str = format(self._number, '02') + format(raw_value, '05')
        self._pyelk.elk_event_send(event)

    def unpack_event_value_read_reply(self, event):
        """Unpack EVENT_VALUE_READ_REPLY.

        Event data format: NNDDDDDF[...]
        NN: Custom setting number number
        DDDDD: 16 bit counter value, ASCII decimal '00000' .. '65535'
        F: Custom setting format (0: Number, 1: Timer, 2: Time of day)
        [...]: If NN is 0, repeat DDDDDF another 19 times for all custom settings
        """
        index = int(event.data_str[0:1])
        offset = None
        data = ''
        if index == 0:
            # must find our result in list of 20
            offset = 2 + (6 * self._index)
        else:
            # only a single result
            offset = 2
        raw_data = int(event.data_str[offset:offset+5])
        data_format = int(event.data_str[offset+5])
        if data_format == self.FORMAT_NUMBER:
            data = raw_data
        elif data_format == self.FORMAT_TIMER:
            data = raw_data
        elif data_format == self.FORMAT_TIME_OF_DAY:
            raw_data = format(raw_data, '04x')
            tod_hour = int(raw_data[0:2])
            tod_minute = int(raw_data[2:4])
            data = format(tod_hour, '02') + ':' + format(tod_minute, '02')
        if self._status == data:
            return
        else:
            self._status = data
            self._format = data_format
            self._updated_at = event.time
            self._callback()
