"""Elk User."""
from collections import namedtuple
from collections import deque
import logging
import time
import traceback

from ..Const import *
from ..Node import Node
from ..Event import Event

_LOGGER = logging.getLogger(__name__)

class User(Node):
    """Represents a User in the Elk."""
    def __init__(self, pyelk=None, number=None):
        """Initializes User object.

        pyelk: Pyelk.Elk object that this object is for (default None).
        number: Index number of this object (default None).
        """
        # Let Node initialize common things
        super().__init__('User', pyelk, number)
        # Initialize Output specific things
        if self._number == 200:
            self._description = 'Unused'
        if self._number == 201:
            self._description = 'Program Code'
        if self._number == 202:
            self._description = 'ELK RP'
        if self._number == 203:
            self._description = 'Quick Arm'

    def description_pretty(self, prefix='User '):
        """Area description, as text string (auto-generated if not set)."""
        return super().description_pretty(prefix)
