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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Fixtures for Testflinger agent tests."""

import pytest

from testflinger_agent.schema import validate


@pytest.fixture
def config(tmp_path):
    """Fixture of a valid agent configuration."""
    for subdir in ("run", "logs", "results"):
        (tmp_path / subdir).mkdir()
    return validate(
        {
            "agent_id": "test01",
            "identifier": "12345-123456",
            "polling_interval": 2,
            "server_address": "127.0.0.1:8000",
            "job_queues": ["test"],
            "location": "nowhere",
            "provision_type": "noprovision",
            "execution_basedir": str(tmp_path / "run"),
            "logging_basedir": str(tmp_path / "logs"),
            "results_basedir": str(tmp_path / "results"),
            "advertised_queues": {"test_queue": "test_queue"},
            "advertised_images": {
                "test_queue": {"test_image": "url: http://foo"}
            },
        }
    )
