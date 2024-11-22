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
Bash completion helper functions module.
"""

from argparse import Namespace

from testflinger_cli.history import TestflingerCliHistory


def job_ids_completer(
    prefix: str,
    parsed_args: Namespace,
    history: TestflingerCliHistory,
    **kwargs,
):
    """Completer for job identifiers."""
    if not hasattr(history, "history"):
        return []
    return history.history.keys()
