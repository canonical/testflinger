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


from datetime import datetime, timezone

from testflinger_common.enums import TestEvent

from testflinger_agent.client import TestflingerClient


class EventEmitter:
    def __init__(
        self,
        job_queue: str,
        webhook: str,
        client: TestflingerClient,
        job_id: str,
    ):
        """
        :param job_queue:
            String representing job_queue the running job belongs to
        :param webhook:
            String url to send status updates to
        :param client:
            TestflingerClient used to post status updates to the server
        :param job_id:
            id for the job on which we want to post updates

        """
        self.job_queue = job_queue
        self.webhook = webhook
        self.events = []
        self.client = client
        self.job_id = job_id

    def emit_event(self, test_event: TestEvent, detail: str = ""):
        if test_event is not None:
            new_event_json = {
                "event_name": test_event,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "detail": detail,
            }
            self.events.append(new_event_json)
            self.client.post_status_update(
                self.job_queue, self.webhook, self.events, self.job_id
            )
