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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Maas2 agent module unit tests."""

import json
import logging
import subprocess
import textwrap
from collections import namedtuple
from unittest.mock import patch

import pytest
import yaml

from testflinger_device_connectors.devices import (
    ProvisioningError,
    RecoveryError,
)
from testflinger_device_connectors.devices.maas2 import Maas2
from testflinger_device_connectors.devices.maas2.maas_storage import (
    MaasStorageError,
)


def test_maas2_agent_invalid_storage(tmp_path):
    """Test maas2 agent raises an exception when storage init fails."""
    config_yaml = tmp_path / "config.yaml"
    config = {"maas_user": "user", "node_id": "abc", "agent_name": "agent001"}
    config_yaml.write_text(yaml.safe_dump(config))

    job_json = tmp_path / "job.json"
    job = {}
    job_json.write_text(json.dumps(job))

    with pytest.raises(MaasStorageError) as err:
        Maas2(config=config_yaml, job_data=job_json)

    # MaasStorageError should also be a subclass of ProvisioningError
    assert isinstance(err.value, ProvisioningError)


def test_maas_cmd_retry(tmp_path):
    """Test that maas commands get retried when the command returns an
    exit code.
    """
    Process = namedtuple("Process", ["returncode", "stdout"])
    with patch(
        "testflinger_device_connectors.devices.maas2.maas2.MaasStorage",
        return_value=None,
    ):
        with (
            patch("subprocess.run", return_value=Process(1, b"error")),
            patch("time.sleep", return_value=None) as mocked_time_sleep,
        ):
            config_yaml = tmp_path / "config.yaml"
            config = {
                "maas_user": "user",
                "node_id": "abc",
                "agent_name": "agent001",
            }
            config_yaml.write_text(yaml.safe_dump(config))

            job_json = tmp_path / "job.json"
            job = {}
            job_json.write_text(json.dumps(job))
            maas2 = Maas2(config=config_yaml, job_data=job_json)
            cmd = "my_maas_cmd"
            with pytest.raises(ProvisioningError) as err:
                maas2.run_maas_cmd_with_retry(cmd)
                assert err.messsage == "error"

            assert mocked_time_sleep.call_count == 6


def test_reset_efi_prioritizes_current_boot_device(tmp_path):
    """Test that reset_efi prioritizes the currently booted network device."""
    Process = namedtuple("Process", ["returncode", "stdout"])

    # Mock efibootmgr output with BootCurrent and multiple IPv4 devices
    efibootmgr_output = textwrap.dedent("""\
        BootCurrent: 0002
        BootOrder: 0000,0001,0002
        Boot0000* ubuntu
        Boot0001* Ethernet 10Gb 2-port Adapter - NIC (PXE IPv4)
        Boot0002* Ethernet 1Gb 4-port Adapter - NIC (PXE IPv4)
    """)

    with patch(
        "testflinger_device_connectors.devices.maas2.maas2.MaasStorage",
        return_value=None,
    ):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Process(0, efibootmgr_output.encode()),  # _get_efi_data
                Process(0, b""),  # _set_efi_data
            ]

            config_yaml = tmp_path / "config.yaml"
            config = {
                "maas_user": "user",
                "node_id": "abc",
                "agent_name": "agent001",
                "device_ip": "10.10.10.10",
            }
            config_yaml.write_text(yaml.safe_dump(config))

            job_json = tmp_path / "job.json"
            job = {}
            job_json.write_text(json.dumps(job))

            maas2 = Maas2(config=config_yaml, job_data=job_json)
            maas2.reset_efi()

            set_efi_call = mock_run.call_args_list[1]
            boot_order_arg = set_efi_call[0][0][-1]
            expected_order = "sudo efibootmgr -o 0002,0001,0000"
            assert expected_order in boot_order_arg


def test_reset_efi_handles_non_ipv4_current_boot(tmp_path):
    """Test that reset_efi handles cases where current boot is not IPv4."""
    Process = namedtuple("Process", ["returncode", "stdout"])

    # Current boot is from hard drive, not network
    efibootmgr_output = textwrap.dedent("""\
        BootCurrent: 0000
        BootOrder: 0000,0001,0002
        Boot0000* ubuntu
        Boot0001* Ethernet 10Gb 2-port Adapter - NIC (PXE IPv4)
        Boot0002* Ethernet 1Gb 4-port Adapter - NIC (PXE IPv4)
    """)

    with patch(
        "testflinger_device_connectors.devices.maas2.maas2.MaasStorage",
        return_value=None,
    ):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Process(0, efibootmgr_output.encode()),  # _get_efi_data
                Process(0, b""),  # _set_efi_data
            ]

            config_yaml = tmp_path / "config.yaml"
            config = {
                "maas_user": "user",
                "node_id": "abc",
                "agent_name": "agent001",
                "device_ip": "10.10.10.10",
            }
            config_yaml.write_text(yaml.safe_dump(config))

            job_json = tmp_path / "job.json"
            job = {}
            job_json.write_text(json.dumps(job))

            maas2 = Maas2(config=config_yaml, job_data=job_json)
            maas2.reset_efi()

            set_efi_call = mock_run.call_args_list[1]
            boot_order_arg = set_efi_call[0][0][-1]
            expected_order = "sudo efibootmgr -o 0001,0002,0000"
            assert expected_order in boot_order_arg


def test_maas_release_succeeds(tmp_path, capsys, caplog):
    """Test MAAS release succeeds and don't return any output."""
    Process = namedtuple("Process", ["returncode", "stdout"])

    # Both release and read return a huge JSON object
    mock_maas_output = json.dumps(
        {
            "owner_data": {},
            "hostname": "fake",
            "system_id": "abc",
            "status_name": "Ready",
            "resource_uri": "/MAAS/api/2.0/machines/abc/",
        }
    )

    with patch(
        "testflinger_device_connectors.devices.maas2.maas2.MaasStorage",
        return_value=None,
    ):
        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.side_effect = [
                Process(0, mock_maas_output.encode()),  # maas release
                Process(0, mock_maas_output.encode()),  # maas read
            ]

            config_yaml = tmp_path / "config.yaml"
            config = {
                "maas_user": "user",
                "node_id": "abc",
                "agent_name": "agent001",
                "device_ip": "10.10.10.10",
            }
            config_yaml.write_text(yaml.safe_dump(config))

            job_json = tmp_path / "job.json"
            job = {}
            job_json.write_text(json.dumps(job))

            maas2 = Maas2(config=config_yaml, job_data=job_json)
            with caplog.at_level(
                logging.INFO,
                logger="testflinger_device_connectors.devices.maas2.maas2",
            ):
                maas2.node_release()

    # Verify release and read where called
    assert mock_run.call_count == 2

    # Verify release command was called correctly and release is logged
    first_call_args = mock_run.call_args_list[0][0][0]
    assert first_call_args == [
        "maas",
        config["maas_user"],
        "machine",
        "release",
        config["node_id"],
    ]
    assert f"Successfully released {config['agent_name']}" in caplog.text

    # Verify release command output was captured but not printed
    captured_output = capsys.readouterr()
    assert mock_run.call_args_list[0][1]["stdout"] == subprocess.PIPE
    assert captured_output.out == ""


def test_maas_release_fails(tmp_path, capsys, caplog):
    """Test MAAS release fails and output is properly logged."""
    Process = namedtuple("Process", ["returncode", "stdout"])

    # Both release and read return a huge JSON object
    mock_maas_output = json.dumps(
        {
            "owner_data": {},
            "hostname": "fake",
            "system_id": "abc",
            "status_name": "Deployed",
            "resource_uri": "/MAAS/api/2.0/machines/abc/",
        }
    )

    with patch(
        "testflinger_device_connectors.devices.maas2.maas2.MaasStorage",
        return_value=None,
    ):
        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.side_effect = [
                Process(0, mock_maas_output.encode()),  # maas release
            ] + [
                Process(0, mock_maas_output.encode())  # maas read (30 times)
            ] * 30

            config_yaml = tmp_path / "config.yaml"
            config = {
                "maas_user": "user",
                "node_id": "abc",
                "agent_name": "agent001",
                "device_ip": "10.10.10.10",
            }
            config_yaml.write_text(yaml.safe_dump(config))

            job_json = tmp_path / "job.json"
            job = {}
            job_json.write_text(json.dumps(job))

            maas2 = Maas2(config=config_yaml, job_data=job_json)
            with (
                caplog.at_level(
                    logging.ERROR,
                    logger="testflinger_device_connectors.devices.maas2.maas2",
                ),
                pytest.raises(RecoveryError),
            ):
                maas2.node_release()

    # Verify no output to console, this is handled by the logger
    captured_output = capsys.readouterr()
    assert captured_output.out == ""

    # Verify errors were logged
    assert (
        f'Device {config["agent_name"]} still in "Deployed" state'
        in caplog.text
    )
    assert mock_maas_output in caplog.text
