# Copyright (C) 2023-2024 Canonical
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
"""Additional views not associated with the API."""

from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from prometheus_client import generate_latest

from testflinger import database
from testflinger.database import mongo

views = Blueprint("testflinger", __name__)


@views.route("/")
def home():
    """Home view."""
    return redirect(url_for("testflinger.agents"))


@views.route("/metrics")
def metrics():
    """Return Prometheus metrics."""
    return generate_latest()


@views.route("/agents")
def agents():
    """Agents view."""
    agent_info = mongo.db.agents.find()
    return render_template("agents.html", agents=agent_info)


@views.route("/agents/<agent_id>")
def agent_detail(agent_id):
    """Agent detail view."""
    default_start_date = (
        datetime.now(tz=timezone.utc) - timedelta(days=2)
    ).strftime("%Y-%m-%d")
    default_stop_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    start_date = request.args.get("start", default_start_date)
    stop_date = request.args.get("stop", default_stop_date)

    # Convert start and stop dates to datetime objects for the query
    start_datetime = datetime.strptime(start_date, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    stop_datetime = datetime.strptime(stop_date, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    ) + timedelta(days=1)

    agent_info = mongo.db.agents.find_one({"name": agent_id})
    if not agent_info:
        response = make_response(
            render_template("agent_not_found.html", agent_id=agent_id)
        )
        response.status_code = 404
        return response

    restricted_queues = database.get_restricted_queues()
    client_permissions = database.get_restricted_queues_owners()

    agent_info["restricted_to"] = {
        queue: client_permissions.get(queue, [])
        if queue in restricted_queues
        else []
        for queue in agent_info.get("queues", [])
    }

    # We want to include the start/stop dates so that default values
    # can be filled in for the date pickers
    agent_info["start"] = start_date
    agent_info["stop"] = stop_date

    agent_info["provision_log"] = database.get_provision_log(
        agent_id,
        start_datetime=start_datetime,
        stop_datetime=stop_datetime,
    )

    if agent_info["provision_log"]:
        agent_info["provision_success_rate"] = int(
            100
            * len(
                [
                    entry
                    for entry in agent_info["provision_log"]
                    if entry["exit_code"] == 0
                ]
            )
            / len(agent_info["provision_log"])
        )
    else:
        # Avoid division by zero
        agent_info["provision_success_rate"] = 0

    return render_template("agent_detail.html", agent=agent_info)


@views.route("/jobs")
def jobs():
    """Jobs view."""
    jobs_data = mongo.db.jobs.find(sort=[("created_at", -1)])
    return render_template("jobs.html", jobs=jobs_data)


@views.route("/jobs/<job_id>")
def job_detail(job_id):
    """Job detail view."""
    job_data = mongo.db.jobs.find_one({"job_id": job_id})
    if not job_data:
        response = make_response(
            render_template("job_not_found.html", job_id=job_id), 404
        )
        return response
    return render_template("job_detail.html", job=job_data)


@views.route("/queues")
def queues():
    """
    Queues view.

    Render a view with all known queues, descriptions if known, and the number
    of jobs in each.
    """
    queue_data = queues_data()
    return render_template("queues.html", queues=queue_data)


def queues_data():
    """Generate data for the queues view, this makes testing easier."""
    # First, get all the advertised queues with descriptions
    queue_data = list(
        mongo.db.queues.find(
            projection={"_id": 0, "name": 1, "description": 1}
        )
    )

    # Get all the queues the agents say they are listening to from agent data
    agent_data = mongo.db.agents.find({}, {"_id": 0, "queues": 1})
    agent_queues_set = {
        queue for agent in agent_data for queue in agent.get("queues", [])
    }
    #    queue for agent in agent_data for queue in agent["queues"]
    advertised_queues_set = {queue["name"] for queue in queue_data}

    # Only keep the ones that weren't also in the advertised queues
    unique_queues_from_agents = agent_queues_set - advertised_queues_set
    for queue_name in unique_queues_from_agents:
        queue_data.append(
            {"name": queue_name, "description": "", "numjobs": 0}
        )

    # Get job counts for each queue
    for queue in queue_data:
        queue["numjobs"] = mongo.db.jobs.count_documents(
            {
                "job_data.job_queue": queue["name"],
                "result_data.job_state": {
                    "$nin": ["complete", "completed", "cancelled"]
                },
            }
        )
    return queue_data


@views.route("/queues/<queue_name>")
def queue_detail(queue_name):
    """Queue detailed view."""
    queue_data = mongo.db.queues.find_one({"name": queue_name})
    if not queue_data:
        # If it's not an advertised queue, create some dummy data
        queue_data = {"name": queue_name, "description": "No description"}

    # Find all the jobs active jobs in this queue
    job_data = mongo.db.jobs.find(
        {
            "job_data.job_queue": queue_name,
            "result_data.job_state": {
                "$nin": ["complete", "completed", "cancelled"]
            },
        }
    )

    # Get the percentiles of wait times for this queue
    wait_times = database.get_queue_wait_times([queue_name])
    try:
        wait_times = wait_times[0]["wait_times"]
    except (IndexError, KeyError):
        wait_times = []
    queue_percentile_data = database.calculate_percentiles(wait_times)

    # Convert the wait times to human-readable strings
    for key, value in queue_percentile_data.items():
        queue_percentile_data[key] = seconds_to_hms(value)

    agents_data = database.get_agents_on_queue(queue_name)

    return render_template(
        "queue_detail.html",
        queue=queue_data,
        jobs=job_data,
        queue_percentile_data=queue_percentile_data,
        agents=agents_data,
    )


def seconds_to_hms(seconds: float) -> str:
    """Convert seconds to a human-readable string."""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
