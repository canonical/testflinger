# Copyright (C) 2020 Canonical
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

import json
import os
import xdg
from collections import OrderedDict
from datetime import datetime


class TestflingerCliHistory:
    def __init__(self):
        self.historyfile = os.path.join(
            xdg.XDG_DATA_HOME, "testflinger-cli-history.json")
        self.load()

    def new(self, job_id, queue):
        submission_time = datetime.now().timestamp()
        self.history[job_id] = dict(
            queue=queue,
            submission_time=submission_time,
            job_state='unknown'
        )
        # limit job history to last 10 jobs
        if len(self.history) > 10:
            self.history.popitem(last=False)
        self.save()

    def load(self):
        if not hasattr(self, 'history'):
            self.history = OrderedDict()
        if os.path.exists(self.historyfile):
            with open(self.historyfile) as f:
                try:
                    self.history.update(json.load(f))
                except Exception:
                    # If there's any error loading the history, ignore it
                    return

    def save(self):
        with open(self.historyfile, 'w') as f:
            json.dump(self.history, f, indent=2)

    def update(self, job_id, state):
        if job_id in self.history:
            self.history[job_id]['job_state'] = state
            self.save()
