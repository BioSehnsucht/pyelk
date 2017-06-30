from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class Task(Node):
    STATUS_OFF = 0
    STATUS_ON = 1

    STATUS_STR = {
        STATUS_OFF : 'Off',
        STATUS_ON : 'On'
    }

    def __init__(self, pyelk = None, number = None):
        """Initializes Task object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super(Task, self).__init__(pyelk, number)
        # Initialize Task specific things
        self._status = self.STATUS_OFF
        self._last_activated = 0

    def description(self):
        """Task description, as text string (auto-generated if not set)."""
        return super(Task, self).description('Task ')

    def turn_on(self):
        """Activate Task.

        Data format: DDD
        DDD: Task number to activate (1 to 32, left zero padded to 3 digits)
        """
        event = Event()
        event._type = Event.EVENT_TASK_ACTIVATE
        event._data_str = format(self._number,'03')
        self._pyelk.elk_event_send(event)

    def turn_off(self):
        """No command sent (tasks can only be activated),
        just ensures the status is set to being off."""
        self._status = self.STATUS_OFF
        self._updated_at = time.time()
        self._callback()

    def dump(self):
        """Dump debugging data, to be removed."""
        _LOGGER.debug('Task Last Activated: {}\n'.format(repr(self._last_changed)))
        _LOGGER.debug('Task Description: {}\n'.format(repr(self.description())))

    def unpack_event_task_update(self, event: Event):
        """Unpack EVENT_TASK_UPDATE.

        Event data format: RRR0
        RRR: Task number that was activated (1 to 32, left zero padded to 3 digits)
        0: Reserved for future use
        """
        data = int(event._data_str[0:3])
        if (self._status == data):
            return
        # We set to off because it's a momentary event, but update the time so
        # things can be triggered from the last_activated
        self._status = self.STATUS_ON
        self._updated_at = event._time
        self._last_activated = event._time
        self._callback()
        time.sleep(1)
        self._status = self.STATUS_OFF
        self._updated_at = event._time
        self._callback()
