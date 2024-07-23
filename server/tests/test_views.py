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
Unit tests for Testflinger views
"""

from datetime import datetime
import re
import mongomock
from mock import patch
from src.views import job_detail, queues_data, agent_detail


def test_queues():
    """
    Test that the queues view gets the right data from both advertised and
    unadvertised queues
    """

    mongo = mongomock.MongoClient()
    mongo.db.queues.insert_many(
        [
            {"name": "advertised_queue1", "description": "desc1"},
            {"name": "advertised_queue2", "description": "desc2"},
        ]
    )
    mongo.db.agents.insert_many(
        [
            {
                "name": "agent1",
                "queues": ["queue2", "queue4", "advertised_queue1"],
            },
            {
                "name": "agent2",
                "queues": ["queue2", "queue4", "advertised_queue2"],
            },
            # There's an unlikely chance that an agent has no queues
            {
                "name": "agent2",
            },
        ]
    )
    mongo.db.jobs.insert_many(
        [
            {"job_data": {"job_queue": "advertised_queue1"}},
            {"job_data": {"job_queue": "advertised_queue1"}},
            {"job_data": {"job_queue": "advertised_queue1"}},
            {"job_data": {"job_queue": "advertised_queue2"}},
            {"job_data": {"job_queue": "advertised_queue2"}},
        ]
    )

    # Get the data from the function we use to generate the view
    with patch("src.views.mongo", mongo):
        data = queues_data()

    # Make sure we found all the queues, not just advertised ones
    assert len(data) == 4

    # Check that advertised queues have descriptions even though they're also
    # in agent queues without one
    advertised_queue1 = [
        queue for queue in data if queue["name"] == "advertised_queue1"
    ]
    assert len(advertised_queue1) == 1
    assert advertised_queue1[0]["description"] == "desc1"
    assert advertised_queue1[0]["numjobs"] == 3
    advertised_queue2 = [
        queue for queue in data if queue["name"] == "advertised_queue2"
    ]
    assert len(advertised_queue2) == 1
    assert advertised_queue2[0]["description"] == "desc2"
    assert advertised_queue2[0]["numjobs"] == 2


def test_agent_detail_no_provision_log(testapp):
    """
    Test that the agent detail page doesn't break when there's no provision log
    """

    mongo = mongomock.MongoClient()
    mongo.db.agents.insert_one(
        {"name": "agent1", "updated_at": datetime.now()}
    )
    with patch("src.views.mongo", mongo):
        with testapp.test_request_context():
            response = agent_detail("agent1")

    pattern = r"Provision success rate for this range:</strong>\s*0%"
    assert re.search(pattern, response)


def test_agent_not_found(testapp):
    """
    Test that the agent_detail fails gracefully when an agent is not found
    """

    mongo = mongomock.MongoClient()
    with patch("src.views.mongo", mongo):
        with testapp.test_request_context():
            response = agent_detail("agent1")

    assert "Agent not found: agent1" in str(response.data)
    assert response.status_code == 404


def test_job_not_found(testapp):
    """
    Test that the job_detail fails gracefully when a job is not found
    """

    mongo = mongomock.MongoClient()
    with patch("src.views.mongo", mongo):
        with testapp.test_request_context():
            response = job_detail("job1")

    assert "Job not found: job1" in str(response.data)
    assert response.status_code == 404
