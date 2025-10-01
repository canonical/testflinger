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
"""Tests for the DefaultDevice runtest secrets injection."""

from testflinger_device_connectors.devices import DefaultDevice


def test_runtest_injects_secrets(mocker):
    """Test that runtest injects secrets from test_data into env."""
    config_data = {}
    job_data = {
        "test_data": {
            "test_cmds": "echo 'test'",
            "secrets": {
                "SECRET_KEY": "secret_value",
                "API_TOKEN": "token_value",
            },
        }
    }

    args = mocker.Mock()

    mocker.patch("builtins.open", mocker.mock_open())
    mocker.patch("yaml.safe_load", return_value=config_data)
    mocker.patch(
        "testflinger_device_connectors.get_test_opportunity",
        return_value=job_data,
    )
    # Patch run_test_cmds to capture the config argument that gets passed to it
    mock_run_test_cmds = mocker.patch(
        "testflinger_device_connectors.run_test_cmds", return_value=0
    )

    DefaultDevice({}).runtest(args)

    # Verify secrets were injected into config["env"]
    call_args = mock_run_test_cmds.call_args
    config = call_args[0][1]

    assert config["env"]["SECRET_KEY"] == "secret_value"
    assert config["env"]["API_TOKEN"] == "token_value"
