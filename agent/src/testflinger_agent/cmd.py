# Copyright (C) 2016-2023 Canonical
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
"""Entrypoint for the testflinger-agent command"""

import logging
import sys

from testflinger_agent import start_agent

logger = logging.getLogger(__name__)


def main():
    """Entrypoint for the testflinger-agent command"""
    try:
        start_agent()
    except KeyboardInterrupt:
        logger.info("Caught interrupt, exiting!")
        sys.exit(0)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception(exc)
