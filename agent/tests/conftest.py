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

"""Shared pytest fixtures for agent tests."""

import pytest


@pytest.fixture
def config(tmp_path):
    """Create a minimal config for testing."""
    return {
        "agent_id": "test01",
        "identifier": "12345-123456",
        "polling_interval": 1,
        "server_address": "127.0.0.1:8000",
        "job_queues": ["test"],
        "location": "nowhere",
        "provision_type": "noprovision",
        "execution_basedir": str(tmp_path / "execution"),
        "logging_basedir": str(tmp_path / "logs"),
        "results_basedir": str(tmp_path / "results"),
    }
