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

from .client import TestflingerClient


class LiveOutputHandler:
    def __init__(self, client: TestflingerClient, job_id: str):
        self.client = client
        self.job_id = job_id

    def __call__(self, data: str):
        self.client.post_live_output(self.job_id, data)


class LogUpdateHandler:
    def __init__(self, log_file: str):
        self.log_file = log_file

    def __call__(self, data: str):
        with open(self.log_file, "a") as log:
            log.write(data)
