"""
PyElk - Python Library for the Elk M1 Gold 
        and Elk M1 EZ8 alarm / integration panels

This module provides an interface to the Elk ASCII protocol,
either using direct serial or via the Elk M1XEP ethernet module.

The Elk devices are products of Elk Products, Inc. The Elk devices 
are both alarm panels and integration devices capable of talking to
various lighting control systems, thermostats, and so on.

Copyright 2017 Jonathan Vaughn
               biosehnsucht+pyelk@gmail.com

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""
from .Elk import Elk


__version__ = '0.1.0'
__author__ = 'Jonathan Vaughn'
__email__ = 'biosehnsucht+pyelk@gmail.com'
__date__ = 'May 2017'
__website__ = 'https://github.com/BioSehnsucht/pyelk'
