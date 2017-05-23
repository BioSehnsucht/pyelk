from collections import namedtuple
from collections import deque
import logging
import serial
import serial.threaded
import time
import traceback

_LOGGER = logging.getLogger(__name__)

class Output(object):
    STATUS_OFF = 0
    STATUS_ON = 1

    STATUS_STR = {
        STATUS_OFF : 'Off',
        STATUS_ON : 'On'
    }

    _status = 0
    _number = 0
    _description = ''
    _updated_at = 0

    def __init__(self, pyelk = None):
        self._pyelk = pyelk

    """
    PyElk.Event.EVENT_OUTPUT_STATUS_REPORT
    """
    def unpack_event_output_status_report(self, event):
        data = event.data_dehex()[self._number-1]
        if (self._status == data):
            return
        self._status = data
        self._updated_at = event._time

    """
    PyElk.Event.EVENT_OUTPUT_UPDATE
    """
    def unpack_event_output_update(self, event):
        data = int(event.data_dehex()[3])
        if (self._status == data):
            return
        self._status = data
        self._updated_at = event._time

    def age(self):
        return time.time() - self._updated_at

    def status(self):
        return self.STATUS_STR[self._status]

    def description(self):
        if (self._description == ''):
            return 'Output ' + str(self._number)
        return self._description

    def dump(self):
        _LOGGER.debug('Output Status: {}\n'.format(repr(self.status())))
        _LOGGER.debug('Output Description: {}\n'.format(repr(self.description())))

