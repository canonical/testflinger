# Copyright (C) 2020-2022 Canonical
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
Testflinger history module
"""

import json
import logging
from collections import OrderedDict
from datetime import datetime

from xdg_base_dirs import xdg_config_home

logger = logging.getLogger(__name__)


class TestflingerCliHistory:
    """History class used for storing job history on a device"""

    def __init__(self):
        config_home = xdg_config_home()
        config_home.mkdir(parents=True, exist_ok=True)
        self.historyfile = config_home / "testflinger-cli-history.json"
        self.history = OrderedDict()
        self.load()

    def new(self, job_id, queue):
        """Add a new job to the history"""
        submission_time = datetime.now().timestamp()
        self.history[job_id] = {
            "queue": queue,
            "submission_time": submission_time,
            "job_state": "unknown",
        }

        # limit job history to last 10 jobs
        if len(self.history) > 10:
            self.history.popitem(last=False)
        self.save()

    def load(self):
        """Load the history file"""
        try:
            with self.historyfile.open(
                encoding="utf-8", errors="ignore"
            ) as history_file:
                self.history.update(json.load(history_file))
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as e:
            # If there's any error loading the history, ignore it
            logging.exception(e)
            logger.error(
                "Error loading history file from %s", self.historyfile
            )

    def save(self):
        """Save the history out to the history file"""
        with self.historyfile.open(
            "w", encoding="utf-8", errors="ignore"
        ) as history_file:
            json.dump(self.history, history_file)

    def update(self, job_id, state):
        """Update job state in the history file"""
        if job_id in self.history:
            self.history[job_id]["job_state"] = state
            self.save()
