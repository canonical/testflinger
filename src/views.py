# Copyright (C) 2023 Canonical
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
Additional views not associated with the API
"""

from flask import Blueprint, render_template
from prometheus_client import generate_latest
from src.database import mongo

views = Blueprint("testflinger", __name__)


@views.route("/metrics")
def metrics():
    """Return Prometheus metrics"""
    return generate_latest()


@views.route("/agents")
def agents():
    """Agents view"""
    agent_info = mongo.db.agents.find()
    return render_template("agents.html", agents=agent_info)


@views.route("/jobs")
def jobs():
    """Jobs view"""
    jobs_data = mongo.db.jobs.find()
    return render_template("jobs.html", jobs=jobs_data)


@views.route("/jobs/<job_id>")
def job_detail(job_id):
    """Job detail view"""
    job_data = mongo.db.jobs.find_one({"job_id": job_id})
    return render_template("job_detail.html", job=job_data)


@views.route("/queues")
def queues():
    """Queues view"""

    # This finds all the publicly advertised queues, but also provides a count
    # of the jobs associated with that queue that are not complete or cancelled
    queue_data = mongo.db.queues.aggregate(
        [
            {
                "$lookup": {
                    "from": "jobs",
                    "localField": "name",
                    "foreignField": "job_data.job_queue",
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$not": {
                                        "$in": [
                                            "$result_data.job_state",
                                            ["complete", "cancelled"],
                                        ]
                                    }
                                }
                            }
                        }
                    ],
                    "as": "queuejobs",
                }
            },
            {
                "$addFields": {
                    "numjobs": {"$size": "$queuejobs"},
                }
            },
            {
                "$project": {
                    "name": 1,
                    "numjobs": 1,
                    "description": 1,
                }
            },
        ]
    )
    return render_template("queues.html", queues=queue_data)
