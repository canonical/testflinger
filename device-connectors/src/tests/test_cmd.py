# Copyright (C) 2024 Canonical
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
"""Tests for the cmd argument parser"""

import pytest
import json

from testflinger_device_connectors.cmd import (
    get_args,
    add_exception_logging_to_file,
)


def test_good_args():
    """Test that we can parse good arguments"""
    argv = ["noprovision", "reserve", "-c", "config.cfg", "job_data.json"]

    args = get_args(argv)

    assert args.device == "noprovision"
    assert args.stage == "reserve"
    assert args.config == "config.cfg"
    assert args.job_data == "job_data.json"


def test_invalid_device():
    """Test that an invalid device raises an exception"""
    argv = ["INVALID", "provision", "-c", "config.cfg", "job_data.json"]

    with pytest.raises(SystemExit) as err:
        get_args(argv)
    assert err.value.code == 2


def test_invalid_stage():
    """Test that an invalid stage raises an exception"""
    argv = ["INVALID", "provision", "-c", "config.cfg", "job_data.json"]

    with pytest.raises(SystemExit) as err:
        get_args(argv)
    assert err.value.code == 2


def test_exception_logging(tmp_path):
    """Tests exception logging decorator that adds file logging"""
    open("device-connector-error.json", "w").close()

    exception_info = {
        "provision_exception_info": {
            "exception_name": "Exception",
            "exception_message": "my message",
            "exception_cause": "Exception('my cause')",
        }
    }

    def test_func(arg1: str, arg2: str):
        raise Exception(arg1) from Exception(arg2)

    func = add_exception_logging_to_file(test_func, "provision")
    try:
        func("my message", "my cause")
    except Exception:
        with open("device-connector-error.json") as error_file:
            assert json.loads(error_file.read()) == exception_info
