# This file is part of nvitop, the interactive NVIDIA-GPU process viewer.
#
# Copyright 2021-2023 Xuehai Pan. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Shortcuts for package ``psutil``.

``psutil`` is a cross-platform library for retrieving information on running processes and system
utilization (CPU, memory, disks, network, sensors) in Python.
"""

from __future__ import annotations

import os as _os
import time as _time
from typing import Callable as _Callable

import psutil as _psutil
from cachetools.func import ttl_cache as _ttl_cache
from psutil import *  # noqa: F403 # pylint: disable=wildcard-import,unused-wildcard-import,redefined-builtin


__all__ = [name for name in _psutil.__all__ if not name.startswith('_')] + [
    'load_average',
    'uptime',
    'memory_percent',
    'swap_percent',
    'ppid_map',
    'reverse_ppid_map',
    'WSL',
    'WINDOWS_SUBSYSTEM_FOR_LINUX',
]
__all__[__all__.index('Error')] = 'PsutilError'


PsutilError = Error  # make alias # noqa: F405
del Error  # noqa: F821 # pylint: disable=undefined-variable


cpu_percent = _ttl_cache(ttl=0.25)(_psutil.cpu_percent)
virtual_memory = _ttl_cache(ttl=0.25)(_psutil.virtual_memory)
swap_memory = _ttl_cache(ttl=0.25)(_psutil.swap_memory)


try:
    load_average: _Callable[[], tuple[float, float, float]] = _ttl_cache(ttl=2.0)(
        _psutil.getloadavg,
    )
    load_average.__doc__ = """Get the system load average."""
except AttributeError:

    def load_average() -> None:
        """Get the system load average."""
        return


def uptime() -> float:
    """Get the system uptime."""
    return _time.time() - _psutil.boot_time()


def memory_percent() -> float:
    """The percentage usage of virtual memory, calculated as ``(total - available) / total * 100``."""
    return virtual_memory().percent


def swap_percent() -> float:
    """The percentage usage of virtual memory, calculated as ``used / total * 100``."""
    return swap_memory().percent


ppid_map: _Callable[[], dict[int, int]] = _psutil._ppid_map  # pylint: disable=protected-access
"""Obtain a ``{pid: ppid, ...}`` dict for all running processes in one shot."""


def reverse_ppid_map() -> dict[int, list[int]]:  # pylint: disable=function-redefined
    """Obtain a ``{ppid: [pid, ...], ...}`` dict for all running processes in one shot."""
    from collections import defaultdict  # pylint: disable=import-outside-toplevel

    tree = defaultdict(list)
    for pid, ppid in ppid_map().items():
        tree[ppid].append(pid)

    return tree


if LINUX:  # noqa: F405
    WSL = _os.getenv('WSL_DISTRO_NAME', default=None)
    if WSL is not None and WSL == '':
        WSL = 'WSL'
else:
    WSL = None
WINDOWS_SUBSYSTEM_FOR_LINUX = WSL
"""The Linux distribution name of the Windows Subsystem for Linux."""
