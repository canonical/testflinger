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
from typing import List, Optional, Union

from testflinger_common.enums import TestEvent

from testflinger_agent.client import TestflingerClient


def normalize_webhooks(
    webhooks: Optional[Union[str, dict, List[Union[str, dict]]]],
) -> List[Union[str, dict]]:
    """Normalize the job webhook definition into a list.

    :param webhooks:
        webhook, list of webhooks, or None
    :return:
        List of webhooks, empty if no webhook was specified
    """
    if not webhooks:
        return []
    if isinstance(webhooks, (str, dict)):
        return [webhooks]
    return list(webhooks)


class EventEmitter:
    def __init__(
        self,
        job_queue: str,
        webhooks: Optional[Union[str, dict, List[Union[str, dict]]]],
        client: TestflingerClient,
        job_id: str,
    ):
        """
        :param job_queue:
            String representing job_queue the running job belongs to
        :param webhooks:
            Webhook, or list of webhooks, to send status updates to
        :param client:
            TestflingerClient used to post status updates to the server
        :param job_id:
            id for the job on which we want to post updates

        """
        self.job_queue = job_queue
        self.webhooks = normalize_webhooks(webhooks)
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
                self.job_queue, self.webhooks, self.events, self.job_id
            )
