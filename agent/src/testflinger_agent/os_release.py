# Copyright (C) 2026 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

"""Query and parse os-release information from a provisioned DUT."""

import logging
import re
import subprocess

logger = logging.getLogger(__name__)

UNKNOWN_RELEASE = "unknown"

SSH_TIMEOUT = 30
SSH_OPTIONS = [
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "BatchMode=yes",
    "-o",
    "LogLevel=ERROR",
]


def query_dut_release(device_ip: str, username: str = "ubuntu") -> str:
    """SSH into a DUT and extract the release label from /etc/os-release.

    Authentication uses SSH key-based auth, no password is required.

    :param device_ip: IP address of the device under test
    :param username: SSH username (default: "ubuntu")
    :return: Release label string, or UNKNOWN_RELEASE on failure
    """
    cmd = [
        "ssh",
        *SSH_OPTIONS,
        f"{username}@{device_ip}",
        "cat /etc/os-release",
    ]

    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=SSH_TIMEOUT,
            check=False,
        )
        if result.returncode != 0:
            logger.warning(
                "Failed to query os-release from %s (rc=%d): %s",
                device_ip,
                result.returncode,
                result.stderr.strip(),
            )
            return UNKNOWN_RELEASE

        os_info = _parse_os_release(result.stdout)
        release = _derive_release_label(os_info)
        logger.info("DUT release detected: %s", release)
        return release

    except subprocess.TimeoutExpired:
        logger.warning("Timed out querying os-release from %s", device_ip)
    except Exception as exc:
        logger.warning("Error querying os-release from %s: %s", device_ip, exc)

    return UNKNOWN_RELEASE


def _parse_os_release(content: str) -> dict:
    """Parse /etc/os-release content into a dictionary.

    :param content: Raw content of /etc/os-release
    :return: Dictionary of key-value pairs
    """
    result = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip('"')
        result[key] = value
    return result


def _derive_release_label(os_info: dict) -> str:
    """Convert parsed os-release data into a release label.

    Follows the logic:
    - Ubuntu Core: "Core {VERSION_ID}" (e.g., "Core 22")
    - Regular Ubuntu: point release if available (e.g., "22.04.5"),
      otherwise VERSION_ID (e.g., "22.04")

    :param os_info: Dictionary from _parse_os_release()
    :return: Release label string
    """
    name = os_info.get("NAME", "")
    version_id = os_info.get("VERSION_ID", "")

    if not version_id:
        return UNKNOWN_RELEASE

    if "Ubuntu Core" in name:
        return f"Core {version_id}"

    # Look for point release in VERSION or PRETTY_NAME
    version = os_info.get("VERSION", os_info.get("PRETTY_NAME", ""))
    point_release_re = re.compile(re.escape(version_id) + r"\.\d+")
    match = point_release_re.search(version)
    if match:
        return match.group(0)

    return version_id
