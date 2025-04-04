# Copyright 2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Abstractions for stopping, starting and managing system services via systemd.

This library assumes that your charm is running on a platform that uses systemd. E.g.,
Centos 7 or later, Ubuntu Xenial (16.04) or later.

For the most part, we transparently provide an interface to a commonly used selection of
systemd commands, with a few shortcuts baked in. For example, service_pause and
service_resume with run the mask/unmask and enable/disable invocations.

Example usage:

```python
from charms.operator_libs_linux.v0.systemd import service_running, service_reload

# Start a service
if not service_running("mysql"):
    success = service_start("mysql")

# Attempt to reload a service, restarting if necessary
success = service_reload("nginx", restart_on_failure=True)
```
"""

__all__ = [  # Don't export `_systemctl`. (It's not the intended way of using this lib.)
    "SystemdError",
    "daemon_reload",
    "service_disable",
    "service_enable",
    "service_failed",
    "service_pause",
    "service_reload",
    "service_restart",
    "service_resume",
    "service_running",
    "service_start",
    "service_stop",
]

import logging
import subprocess

logger = logging.getLogger(__name__)

# The unique Charmhub library identifier, never change it
LIBID = "045b0d179f6b4514a8bb9b48aee9ebaf"

# Increment this major API version when introducing breaking changes
LIBAPI = 1

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 4


class SystemdError(Exception):
    """Custom exception for SystemD related errors."""


def _systemctl(*args: str, check: bool = False) -> int:
    """Control a system service using systemctl.

    Args:
        *args: Arguments to pass to systemctl.
        check: Check the output of the systemctl command. Default: False.

    Returns:
        Returncode of systemctl command execution.

    Raises:
        SystemdError: Raised if calling systemctl returns a non-zero returncode and check is True.
    """
    cmd = ["systemctl", *args]
    logger.debug(f"Executing command: {cmd}")
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            check=check,
        )
        logger.debug(
            f"Command {cmd} exit code: {proc.returncode}. systemctl output:\n{proc.stdout}"
        )
        return proc.returncode
    except subprocess.CalledProcessError as e:
        raise SystemdError(
            f"Command {cmd} failed with returncode {e.returncode}. systemctl output:\n{e.stdout}"
        )


def service_running(service_name: str) -> bool:
    """Report whether a system service is running.

    Args:
        service_name: The name of the service to check.

    Return:
        True if service is running/active; False if not.
    """
    # If returncode is 0, this means that is service is active.
    return _systemctl("--quiet", "is-active", service_name) == 0


def service_failed(service_name: str) -> bool:
    """Report whether a system service has failed.

    Args:
        service_name: The name of the service to check.

    Returns:
        True if service is marked as failed; False if not.
    """
    # If returncode is 0, this means that the service has failed.
    return _systemctl("--quiet", "is-failed", service_name) == 0


def service_start(*args: str) -> bool:
    """Start a system service.

    Args:
        *args: Arguments to pass to `systemctl start` (normally the service name).

    Returns:
        On success, this function returns True for historical reasons.

    Raises:
        SystemdError: Raised if `systemctl start ...` returns a non-zero returncode.
    """
    return _systemctl("start", *args, check=True) == 0


def service_stop(*args: str) -> bool:
    """Stop a system service.

    Args:
        *args: Arguments to pass to `systemctl stop` (normally the service name).

    Returns:
        On success, this function returns True for historical reasons.

    Raises:
        SystemdError: Raised if `systemctl stop ...` returns a non-zero returncode.
    """
    return _systemctl("stop", *args, check=True) == 0


def service_restart(*args: str) -> bool:
    """Restart a system service.

    Args:
        *args: Arguments to pass to `systemctl restart` (normally the service name).

    Returns:
        On success, this function returns True for historical reasons.

    Raises:
        SystemdError: Raised if `systemctl restart ...` returns a non-zero returncode.
    """
    return _systemctl("restart", *args, check=True) == 0


def service_enable(*args: str) -> bool:
    """Enable a system service.

    Args:
        *args: Arguments to pass to `systemctl enable` (normally the service name).

    Returns:
        On success, this function returns True for historical reasons.

    Raises:
        SystemdError: Raised if `systemctl enable ...` returns a non-zero returncode.
    """
    return _systemctl("enable", *args, check=True) == 0


def service_disable(*args: str) -> bool:
    """Disable a system service.

    Args:
        *args: Arguments to pass to `systemctl disable` (normally the service name).

    Returns:
        On success, this function returns True for historical reasons.

    Raises:
        SystemdError: Raised if `systemctl disable ...` returns a non-zero returncode.
    """
    return _systemctl("disable", *args, check=True) == 0


def service_reload(service_name: str, restart_on_failure: bool = False) -> bool:
    """Reload a system service, optionally falling back to restart if reload fails.

    Args:
        service_name: The name of the service to reload.
        restart_on_failure:
            Boolean indicating whether to fall back to a restart if the reload fails.

    Returns:
        On success, this function returns True for historical reasons.

    Raises:
        SystemdError: Raised if `systemctl reload|restart ...` returns a non-zero returncode.
    """
    try:
        return _systemctl("reload", service_name, check=True) == 0
    except SystemdError:
        if restart_on_failure:
            return service_restart(service_name)
        else:
            raise


def service_pause(service_name: str) -> bool:
    """Pause a system service.

    Stops the service and prevents the service from starting again at boot.

    Args:
        service_name: The name of the service to pause.

    Returns:
        On success, this function returns True for historical reasons.

    Raises:
        SystemdError: Raised if service is still running after being paused by systemctl.
    """
    _systemctl("disable", "--now", service_name)
    _systemctl("mask", service_name)

    if service_running(service_name):
        raise SystemdError(f"Attempted to pause {service_name!r}, but it is still running.")

    return True


def service_resume(service_name: str) -> bool:
    """Resume a system service.

    Re-enable starting the service again at boot. Start the service.

    Args:
        service_name: The name of the service to resume.

    Returns:
        On success, this function returns True for historical reasons.

    Raises:
        SystemdError: Raised if service is not running after being resumed by systemctl.
    """
    _systemctl("unmask", service_name)
    _systemctl("enable", "--now", service_name)

    if not service_running(service_name):
        raise SystemdError(f"Attempted to resume {service_name!r}, but it is not running.")

    return True


def daemon_reload() -> bool:
    """Reload systemd manager configuration.

    Returns:
        On success, this function returns True for historical reasons.

    Raises:
        SystemdError: Raised if `systemctl daemon-reload` returns a non-zero returncode.
    """
    return _systemctl("daemon-reload", check=True) == 0
