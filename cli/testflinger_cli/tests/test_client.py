# Copyright (C) 2024 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
Unit tests for the Client class
"""

import logging
import pytest
import requests

from testflinger_cli.client import Client


def test_get_warning_10_failures(caplog, requests_mock):
    """Test that a warning is logged when 10 consecutive failures occur"""
    caplog.set_level(logging.WARNING)
    requests_mock.get(
        "http://testflinger/test", exc=requests.exceptions.ConnectionError
    )
    client = Client("http://testflinger")
    for _ in range(9):
        with pytest.raises(requests.exceptions.ConnectionError):
            client.get("test")
        assert (
            "Error communicating with the server for the past 10 requests"
            not in caplog.text
        )
    with pytest.raises(requests.exceptions.ConnectionError):
        client.get("test")
    assert (
        "Error communicating with the server for the past 10 requests"
        in caplog.text
    )
