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

"""Tests for os_release module."""

import subprocess
from unittest.mock import patch

from testflinger_agent.os_release import (
    UNKNOWN_RELEASE,
    _derive_release_label,
    _parse_os_release,
    query_dut_release,
)

# Sample /etc/os-release contents for different Ubuntu variants

JAMMY_OS_RELEASE = """\
PRETTY_NAME="Ubuntu 22.04.5 LTS"
NAME="Ubuntu"
VERSION_ID="22.04"
VERSION="22.04.5 LTS (Jammy Jellyfish)"
VERSION_CODENAME=jammy
ID=ubuntu
ID_LIKE=debian
"""

NOBLE_OS_RELEASE = """\
PRETTY_NAME="Ubuntu 24.04 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04 LTS (Noble Numbat)"
VERSION_CODENAME=noble
ID=ubuntu
ID_LIKE=debian
"""

CORE22_OS_RELEASE = """\
NAME="Ubuntu Core"
VERSION_ID="22"
ID=ubuntu-core
PRETTY_NAME="Ubuntu Core 22"
"""

CORE20_OS_RELEASE = """\
NAME="Ubuntu Core"
VERSION_ID="20"
ID=ubuntu-core
PRETTY_NAME="Ubuntu Core 20"
"""


class TestParseOsRelease:
    def test_basic_parsing(self):
        result = _parse_os_release(JAMMY_OS_RELEASE)
        assert result["NAME"] == "Ubuntu"
        assert result["VERSION_ID"] == "22.04"
        assert result["VERSION"] == "22.04.5 LTS (Jammy Jellyfish)"

    def test_unquoted_values(self):
        result = _parse_os_release(JAMMY_OS_RELEASE)
        assert result["VERSION_CODENAME"] == "jammy"

    def test_empty_input(self):
        assert _parse_os_release("") == {}

    def test_malformed_lines(self):
        content = 'no-equals\n\nNAME="Ubuntu"\n'
        result = _parse_os_release(content)
        assert result == {"NAME": "Ubuntu"}


class TestDeriveReleaseLabel:
    def test_ubuntu_point_release(self):
        os_info = _parse_os_release(JAMMY_OS_RELEASE)
        assert _derive_release_label(os_info) == "22.04.5"

    def test_ubuntu_base_release(self):
        os_info = _parse_os_release(NOBLE_OS_RELEASE)
        assert _derive_release_label(os_info) == "24.04"

    def test_ubuntu_core(self):
        os_info = _parse_os_release(CORE22_OS_RELEASE)
        assert _derive_release_label(os_info) == "Core 22"

    def test_ubuntu_core_20(self):
        os_info = _parse_os_release(CORE20_OS_RELEASE)
        assert _derive_release_label(os_info) == "Core 20"

    def test_missing_version_id(self):
        assert _derive_release_label({"NAME": "Ubuntu"}) == UNKNOWN_RELEASE

    def test_empty_dict(self):
        assert _derive_release_label({}) == UNKNOWN_RELEASE


class TestQueryDutRelease:
    @patch("testflinger_agent.os_release.subprocess.run")
    def test_successful_query(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=JAMMY_OS_RELEASE, stderr=""
        )
        assert query_dut_release("10.0.0.1") == "22.04.5"

    @patch("testflinger_agent.os_release.subprocess.run")
    def test_ssh_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=255, stdout="", stderr="Connection refused"
        )
        assert query_dut_release("10.0.0.1") == UNKNOWN_RELEASE

    @patch("testflinger_agent.os_release.subprocess.run")
    def test_ssh_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=30)
        assert query_dut_release("10.0.0.1") == UNKNOWN_RELEASE

    @patch("testflinger_agent.os_release.subprocess.run")
    def test_unexpected_exception(self, mock_run):
        mock_run.side_effect = OSError("No such file")
        assert query_dut_release("10.0.0.1") == UNKNOWN_RELEASE
