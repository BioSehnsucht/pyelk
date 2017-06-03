from collections import namedtuple
from collections import deque
import logging
import time
import traceback

_LOGGER = logging.getLogger(__name__)

class Node(object):
    def __init__(self, pyelk = None, number = None):
        """Initializes Node object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Area the object is assocaited with
        self._area = None
        # Index number of this object
        self._number = number
        # Device enabled ?
        self._enabled = True
        # Status of the object
        self._status = None
        # Description of the object
        self._description = None
        # Time object was last updated at
        self._updated_at = None
        # Callback methods for updates
        self._update_callbacks = []
        # Pyelk.Elk object that this object is for
        self._pyelk = pyelk

    def callback_add(self, method):
        """Add a method to list of callbacks to be called on update."""
        self._update_callbacks.append(method)

    def callback_remove(self, method):
        """Remove a method from list of callbacks to be called on update."""
        self._update_callbacks.remove(method)

    def age(self):
        """Age of the current object state (time since last update)."""
        return time.time() - self._updated_at

    def status(self):
        """Current status, as text string."""
        return self.STATUS_STR[self._status]

    def description(self, prefix = 'Node '):
        """Object description, as text string (auto-generated if not set).

        prefix: Prefix to compare against / auto-generate with.
        """
        if (self._description is None) or (self._description == '') \
        or (self._description == prefix.strip() + format(self._number,'02')) \
        or (self._description == prefix.strip() + format(self._number,'03')) \
        or (self._description == prefix + format(self._number,'02')) \
        or (self._description == prefix + format(self._number,'03')):
            # If no description set, or it's the default (with zero
            # padding to 2 or 3 digits) return a nicer default.
            return prefix + str(self._number)
        return self._description

    def _callback(self):
        """Perform update callback, if possible."""
        for callback in  self._update_callbacks:
            callback()
