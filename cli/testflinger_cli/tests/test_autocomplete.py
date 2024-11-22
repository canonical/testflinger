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
Unit tests for autocomplete helper functions.
"""

from argparse import Namespace
from unittest.mock import MagicMock
from collections import OrderedDict

from testflinger_cli.autocomplete import job_ids_completer


def test_job_ids_completer_prefix():
    """job_ids_completer should only suggest items that match the prefix."""
    history = MagicMock(
        history=OrderedDict(
            {
                "a48118d7-e57c-4ea7-a405-2c2049a50ede": {...},
                "afea96e9-2943-4c95-8aa9-e3ae3588c899": {...},
                "1b2e8d33-0cac-424b-801e-da8cfe5c2a37": {...},
                "77212a29-bffb-457a-96b1-1b535a74d3ef": {...},
            }
        )
    )
    suggestions = list(job_ids_completer("a", Namespace(), history))
    assert suggestions == [
        "a48118d7-e57c-4ea7-a405-2c2049a50ede",
        "afea96e9-2943-4c95-8aa9-e3ae3588c899",
    ]
