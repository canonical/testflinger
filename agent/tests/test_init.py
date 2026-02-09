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

from pathlib import Path
from unittest.mock import patch

import testflinger_agent


class TestAgentArgs:
    @patch("sys.argv", ["testflinger-agent", "-c", "test.conf"])
    def test_default_token_file(self):
        """Test parse_args sets the default token file path."""
        args = testflinger_agent.parse_args()

        assert args.token_file == Path(
            "/var/lib/testflinger-agent/refresh_token"
        )

    @patch(
        "sys.argv",
        [
            "testflinger-agent",
            "-c",
            "test.conf",
            "--token-file",
            "/tmp/custom_token",
        ],
    )
    def test_custom_token_file(self):
        """Test parse_args accepts a custom token file path."""
        args = testflinger_agent.parse_args()

        assert args.token_file == Path("/tmp/custom_token")
