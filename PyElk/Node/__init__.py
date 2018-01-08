"""Elk Node."""
from collections import namedtuple
from collections import deque
from inspect import signature
import logging
import time
import traceback

_LOGGER = logging.getLogger(__name__)

class Node(object):
    """Base object for other Elk object types."""
    STATUS_STR = {}

    def __init__(self, classname=None, pyelk=None, number=0):
        """Initializes Node object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Name of class
        self._classname = classname
        # Area the object is assocaited with (1-based)
        self._area = None
        # Area (0-based)
        self._area_index = None
        # Index number of this object (0-based)
        self._index = number
        # Index number of this object (1-based)
        self._number = number+1
        # Device enabled ?
        self._enabled = True
        # Device included (true) /excluded (false) ?
        self._included = False
        # Status of the object
        self._status = None
        # Description of the object
        self._description = None
        # Time object was last updated at
        self._updated_at = 0
        # Callback methods for updates
        self._update_callbacks = []
        # Pyelk.Elk object that this object is for
        self._pyelk = pyelk

    def state_save(self):
        """Returns a save state object for fast load functionality."""
        state = {}
        state['area'] = self._area
        state['enabled'] = self._enabled
        state['included'] = self._included
        state['status'] = self._status
        state['description'] = self._description
        return state

    def state_load(self, state):
        """Loads a save state object for fast load functionality."""
        for state_key in state:
            if state_key == 'area':
                self.area = state['area']
            elif state_key == 'enabled':
                self.enabled = state['enabled']
            elif state_key == 'included':
                self.included = state['included']
            elif state_key == 'status':
                self.status = state['status']
            elif state_key == 'description':
                self.description = state['description']
        return

    @property
    def classname(self):
        """Returns the class name of this class."""
        return self._classname

    @property
    def area(self):
        """Returns Area this node is associated with."""
        return self._area

    @area.setter
    def area(self, value):
        """Sets Area this node is associated with."""
        if isinstance(value, int):
            self._area = value
            self._area_index = self._area-1

    @property
    def number(self):
        """Returns node number (1-based) of this node."""
        return self._number

    @number.setter
    def number(self, value):
        """Sets node number (1-based) of this node."""
        if isinstance(value, int):
            self._number = value
            self._index = self._number - 1

    @property
    def enabled(self):
        """Returns whether this node is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        """Sets the enabled state of this node."""
        if isinstance(value, bool):
            self._enabled = value

    @property
    def included(self):
        """Returns whether this node is included."""
        return self._included

    @included.setter
    def included(self, value):
        """Sets the included state of this node."""
        if isinstance(value, bool):
            self._included = value

    @property
    def description(self):
        """Returns the description of this node."""
        return self._description

    @description.setter
    def description(self, value):
        """Returns the description of this node, prettified if possible."""
        if isinstance(value, str):
            self._description = value

    @property
    def status(self):
        """Returns status of this node."""
        return self._status

    @status.setter
    def status(self, value):
        """Sets status of this node."""
        self._status = value

    @property
    def updated_at(self):
        """Returns last updated timestamp."""
        return self._updated_at

    @updated_at.setter
    def updated_at(self, value):
        """Sets last updated timestamp."""
        self._updated_at = value

    def callback_add(self, method):
        """Add a method to list of callbacks to be called on update."""
        self._update_callbacks.append(method)

    def callback_remove(self, method):
        """Remove a method from list of callbacks to be called on update."""
        self._update_callbacks.remove(method)

    def age(self):
        """Age of the current object state (time since last update)."""
        return time.time() - self._updated_at

    def status_pretty(self):
        """Current status, as text string."""
        if self._status is not None:
            return self.STATUS_STR[self._status]
        return 'Unknown'

    def description_pretty(self, prefix='Node '):
        """Object description, as text string (auto-generated if not set).

        prefix: Prefix to compare against / auto-generate with.
        """
        if (self._description is None) or (self._description == '') \
        or (self._description == prefix.strip() + format(self._number, '02')) \
        or (self._description == prefix.strip() + format(self._number, '03')) \
        or (self._description == prefix + format(self._number, '02')) \
        or (self._description == prefix + format(self._number, '03')):
            # If no description set, or it's the default (with zero
            # padding to 2 or 3 digits) return a nicer default.
            return prefix + str(self._number)
        return self._description

    def _callback(self, data=None):
        """Perform update callback, if possible."""
        for callback in self._update_callbacks:
            sig = signature(callback)
            if len(sig.parameters) == 0:
                callback()
            if len(sig.parameters) == 1:
                callback(self)
            if len(sig.parameters) == 2:
                callback(self, data)
        # If there were no callbacks to be made, make a call upwards
        # We may have new devices that need to be handled
        if len(self._update_callbacks) == 0 and self._pyelk is not None:
            self._pyelk.promoted_callback(self, data)

    def callback_trigger(self, data=None):
        """Trigger a callback."""
        self._callback(data)
