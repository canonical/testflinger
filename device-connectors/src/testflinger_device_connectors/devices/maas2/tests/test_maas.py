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

from testflinger_device_connectors.devices import (
    ProvisioningError,
    RecoveryError,
)
from testflinger_device_connectors.devices.maas2 import Maas2
from testflinger_device_connectors.devices.maas2.maas_storage import (
    MaasStorageError,
)


def test_maas2_agent_invalid_storage(mock_maas_storage, mock_config_file):
    """Test maas2 agent raises an exception when storage init fails."""
    mock_maas_storage.side_effect = MaasStorageError

    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({}))

    with pytest.raises(MaasStorageError) as err:
        Maas2(config=mock_config_file, job_data=job_json)

    # MaasStorageError should also be a subclass of ProvisioningError
    assert isinstance(err.value, ProvisioningError)


def test_maas_cmd_retry(mock_config_file):
    """Test that maas commands get retried when the command returns an
    exit code.
    """
    Process = namedtuple("Process", ["returncode", "stdout"])

    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({}))

    with (
        patch("subprocess.run", return_value=Process(1, b"error")),
        patch("time.sleep", return_value=None) as mocked_time_sleep,
    ):
        maas2 = Maas2(config=mock_config_file, job_data=job_json)
        cmd = ["my_maas_cmd"]
        with pytest.raises(ProvisioningError) as err:
            maas2.run_maas_cmd_with_retry(cmd)

        assert "error" in str(err.value)
        assert mocked_time_sleep.call_count == 6


def test_reset_efi_prioritizes_current_boot_device(mock_config_file):
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

    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({}))

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            Process(0, efibootmgr_output.encode()),  # _get_efi_data
            Process(0, b""),  # _set_efi_data
        ]

        maas2 = Maas2(config=mock_config_file, job_data=job_json)
        maas2.reset_efi()

        set_efi_call = mock_run.call_args_list[1]
        boot_order_arg = set_efi_call[0][0][-1]
        expected_order = "sudo efibootmgr -o 0002,0001,0000"
        assert expected_order in boot_order_arg


def test_reset_efi_handles_non_ipv4_current_boot(mock_config_file):
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

    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({}))

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            Process(0, efibootmgr_output.encode()),  # _get_efi_data
            Process(0, b""),  # _set_efi_data
        ]

        maas2 = Maas2(config=mock_config_file, job_data=job_json)
        maas2.reset_efi()

        set_efi_call = mock_run.call_args_list[1]
        boot_order_arg = set_efi_call[0][0][-1]
        expected_order = "sudo efibootmgr -o 0001,0002,0000"
        assert expected_order in boot_order_arg


def test_maas_release_succeeds(mock_config_file, mock_config, capsys, caplog):
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

    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({}))

    with patch("subprocess.run") as mock_run, patch("time.sleep"):
        mock_run.side_effect = [
            Process(0, mock_maas_output.encode()),  # maas release
            Process(0, mock_maas_output.encode()),  # maas read
        ]

        maas2 = Maas2(config=mock_config_file, job_data=job_json)
        with caplog.at_level(
            logging.INFO,
            logger="testflinger_device_connectors.devices.maas2.maas2",
        ):
            maas2.node_release()

    # Verify release and read where called
    assert mock_run.call_count == 2

    # Verify release command was called correctly
    first_call_args = mock_run.call_args_list[0][0][0]
    assert first_call_args == [
        "maas",
        mock_config["maas_user"],
        "machine",
        "release",
        mock_config["node_id"],
    ]

    # Verify release command output was captured but not printed
    captured_output = capsys.readouterr()
    assert mock_run.call_args_list[0][1]["stdout"] == subprocess.PIPE
    assert captured_output.out == ""


def test_maas_release_fails(mock_config_file, mock_config, capsys, caplog):
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

    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({}))

    with patch("subprocess.run") as mock_run, patch("time.sleep"):
        mock_run.side_effect = [
            Process(0, mock_maas_output.encode()),  # maas release
        ] + [
            Process(0, mock_maas_output.encode())  # maas read (30 times)
        ] * 30

        maas2 = Maas2(config=mock_config_file, job_data=job_json)
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
        f'Device {mock_config["agent_name"]} still in "Deployed" state'
        in caplog.text
    )
    assert mock_maas_output in caplog.text


def test_set_flat_storage_layout_no_output(
    mock_config_file, mock_config, capsys
):
    """Test set_flat_storage_layout does not print any output."""
    Process = namedtuple("Process", ["returncode", "stdout"])

    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({}))

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Process(0, b"storage layout set")

        maas2 = Maas2(config=mock_config_file, job_data=job_json)
        maas2.set_flat_storage_layout()

    # Verify command was called
    assert mock_run.call_count == 1

    # Verify set-storage-layout command was called correctly
    call_args = mock_run.call_args_list[0][0][0]
    assert call_args == [
        "maas",
        mock_config["maas_user"],
        "machine",
        "set-storage-layout",
        mock_config["node_id"],
        "storage_layout=flat",
    ]

    # Verify output was captured and not printed to console
    captured_output = capsys.readouterr()
    assert mock_run.call_args_list[0][1]["stdout"] == subprocess.PIPE
    assert captured_output.out == ""


def test_provision_defaults_to_jammy(mock_config_file):
    """Test that provision defaults to jammy when no distro is specified."""
    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({"provision_data": {}}))

    maas2 = Maas2(config=mock_config_file, job_data=job_json)

    # Mock the deploy_node method to verify it's called with jammy
    with patch.object(maas2, "deploy_node") as mock_deploy:
        maas2.provision()

        # Verify deploy_node was called with jammy as the default distro
        mock_deploy.assert_called_once_with("jammy", None, None, None, False)


@patch.object(Maas2, "run_maas_cmd_with_retry")
def test_get_maas_version(mock_run_maas_cmd, mock_config_file):
    """Test that get_maas_version returns the expected MAAS version tuple."""
    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({"provision_data": {"ephemeral": True}}))

    maas2 = Maas2(config=mock_config_file, job_data=job_json)

    mock_run_maas_cmd.return_value = subprocess.CompletedProcess(
        args=["maas", "user", "version", "read"],
        returncode=0,
        stdout=json.dumps({"version": "3.5.0"}).encode(),
    )
    version = maas2.get_maas_version()
    assert version == (3, 5, 0)
    mock_run_maas_cmd.assert_called_once_with(
        ["maas", "user", "version", "read"],
        max_retries=3,
        backoff_start=10,
    )


@patch.object(Maas2, "run_maas_cmd_with_retry")
def test_get_maas_version_returns_none_on_empty_response(
    mock_run_maas_cmd, mock_config_file
):
    """Test that get_maas_version returns None when version key is absent."""
    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({"provision_data": {"ephemeral": True}}))

    maas2 = Maas2(config=mock_config_file, job_data=job_json)

    mock_run_maas_cmd.return_value = subprocess.CompletedProcess(
        args=["maas", "user", "version", "read"],
        returncode=0,
        stdout=json.dumps({}).encode(),
    )
    assert maas2.get_maas_version() is None
    mock_run_maas_cmd.assert_called_once_with(
        ["maas", "user", "version", "read"],
        max_retries=3,
        backoff_start=10,
    )


@patch.object(Maas2, "run_maas_cmd_with_retry")
def test_get_maas_version_returns_none_on_provisioning_error(
    mock_run_maas_cmd, mock_config_file, caplog
):
    """Test that get_maas_version returns None on ProvisioningError."""
    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({"provision_data": {"ephemeral": True}}))

    maas2 = Maas2(config=mock_config_file, job_data=job_json)

    mock_run_maas_cmd.side_effect = ProvisioningError("maas command failed")

    assert maas2.get_maas_version() is None
    assert "Unable to determine MAAS version" in caplog.text
    assert "Proceeding without ephemeral deployment" in caplog.text


@patch("time.sleep")
@patch.object(Maas2, "check_test_image_booted", return_value=True)
@patch.object(Maas2, "node_status", return_value="Deployed")
@patch.object(Maas2, "run_maas_cmd_with_retry")
@patch.object(Maas2, "set_flat_storage_layout")
@patch.object(Maas2, "recover")
@patch.object(Maas2, "get_maas_version", return_value=(3, 5, 0))
def test_get_maas_version_called_on_ephemeral(
    mock_get_version,
    mock_recover,
    mock_flat_storage,
    mock_run_cmd,
    mock_node_status,
    mock_check_booted,
    mock_sleep,
    mock_config_file,
):
    """Test get_maas_version is called when ephemeral is True in job data."""
    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({"provision_data": {"ephemeral": True}}))

    maas2 = Maas2(config=mock_config_file, job_data=job_json)
    maas2.deploy_node(ephemeral=True)

    mock_get_version.assert_called_once()


@patch("time.sleep")
@patch.object(Maas2, "check_test_image_booted", return_value=True)
@patch.object(Maas2, "node_status", return_value="Deployed")
@patch.object(Maas2, "run_maas_cmd_with_retry")
@patch.object(Maas2, "set_flat_storage_layout")
@patch.object(Maas2, "recover")
@patch.object(Maas2, "get_maas_version", return_value=(3, 4, 0))
def test_ephemeral_deploy_skipped_on_old_maas_version(
    mock_get_version,
    mock_recover,
    mock_flat_storage,
    mock_run_cmd,
    mock_node_status,
    mock_check_booted,
    mock_sleep,
    mock_config_file,
):
    """Test ephemeral_deploy=true is not sent when MAAS version < 3.5.0."""
    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({"provision_data": {"ephemeral": True}}))

    maas2 = Maas2(config=mock_config_file, job_data=job_json)
    maas2.deploy_node(ephemeral=True)

    # run_maas_cmd_with_retry is called twice: allocate (0) and deploy (1)
    deploy_cmd = mock_run_cmd.call_args_list[1][0][0]
    assert "ephemeral_deploy=true" not in deploy_cmd


@patch("time.sleep")
@patch.object(Maas2, "check_test_image_booted", return_value=True)
@patch.object(Maas2, "node_status", return_value="Deployed")
@patch.object(Maas2, "run_maas_cmd_with_retry")
@patch.object(Maas2, "set_flat_storage_layout")
@patch.object(Maas2, "recover")
@patch.object(Maas2, "get_maas_version", return_value=(3, 5, 0))
def test_non_ephemeral_deploy(
    mock_get_version,
    mock_recover,
    mock_flat_storage,
    mock_run_cmd,
    mock_node_status,
    mock_check_booted,
    mock_sleep,
    mock_config_file,
):
    """Test ephemeral_deploy=true is not sent when ephemeral is False."""
    job_json = mock_config_file.parent / "job.json"
    job_json.write_text(json.dumps({"provision_data": {"ephemeral": False}}))

    maas2 = Maas2(config=mock_config_file, job_data=job_json)
    maas2.deploy_node(ephemeral=False)

    # run_maas_cmd_with_retry is called twice: allocate (0) and deploy (1)
    deploy_cmd = mock_run_cmd.call_args_list[1][0][0]
    assert "ephemeral_deploy=true" not in deploy_cmd
