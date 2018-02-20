from collections import deque
import logging
import time
import traceback
import threading
import serial
import serial.threaded

_LOGGER = logging.getLogger(__name__)

class SerialInputHandler(serial.threaded.LineReader):
    """LaneHandler implementation for serial.threaded."""

    def set_pyelk(self, pyelk):
        """Sets the pyelk instance to use."""
        self._pyelk = pyelk
        #self._queue = deque(maxlen=1000)
        #self._pyelk._queue_incoming_elk_events = self._queue

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
        self._pyelk._connection._connection_output.stop()
        if exc:
            traceback.print_exc(exc)

class SerialOutputHandler(object):
    """SerialOutputHandler handles outputting events to serial.threaded via deque."""

    def set_pyelk(self, pyelk):
        """Sets the pyelk instance to use."""
        self._pyelk = pyelk
        self._queue = deque(maxlen=1000)
        self._pyelk._queue_outgoing_elk_events = self._queue

    def __init__(self, ratelimit=1):
        """Setup output handler."""
        self._pyelk = None
        self._interval = 1.0 / ratelimit
        self._stopping = False
        self._event = threading.Event()
        thread = threading.Thread(target=self.run, args=())
        thread.start()

    def queue(self):
        return self._queue

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
        pending = False
        self._event.wait()
        while not self._stopping:
            if len(self._queue) == 0:
                self._event.wait()
                self._event.clear()
            _LOGGER.debug('woke up send queue : ' + str(len(self._queue)))
            for event in list(self._queue):
                # Only send events that aren't in the future
                if event.time <= time.time():
                    self._pyelk.elk_event_send_actual(event)
                    self._queue.remove(event)
                    # If retries is greater than 0 and we have an expect
                    if (event.retries > 0) and (len(event.expect) > 0):
                        event.retries = event.retries - 1
                        event.time = time.time() + event.retry_delay
                        # Queue the retry
                        self._queue.append(event)
                    # Sleep after sending to avoid flooding
                    time.sleep(self._interval)
            # Sleep if more events not yet able to be sent
            if len(self._queue) > 0:
                time.sleep(self._interval)

class Connection():
    def __init__(self):
        self._elkrp_connected = False
        self._connection_protocol = None
        self._connection_thread = None
        self._connection_output = None

    def __del__(self):
        """Shutdown communications."""
        if self._connection_thread is not None:
            self._connection_output.stop()
            #self._connection_output.close()
            self._connection_thread.close()

    @property
    def connected(self):
        """True if connected to Elk panel."""
        if self._connection_thread:
            return self._connection_thread.alive and self._connection_thread.serial.is_open
        return False

    def connect(self, pyelk, address, ratelimit):
        """Connect to the Elk panel.

        address: Host to connect to in either
        "socket://IP.Add.re.ss:Port" or "/dev/ttyUSB0" format.
        ratelimit: rate limit for outgoing events
        """
        self._connection = serial.serial_for_url(address, timeout=1)
        self._connection_thread = serial.threaded.ReaderThread(self._connection, SerialInputHandler)
        self._connection_thread.start()
        self._connection_transport, self._connection_protocol = self._connection_thread.connect()
        self._connection_protocol.set_pyelk(pyelk)
        self._connection_output = SerialOutputHandler(ratelimit)
        self._connection_output.set_pyelk(pyelk)
        _LOGGER.debug('ReaderThread created')
