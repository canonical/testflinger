# Copyright (C) 2026 Canonical
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
"""Event handling functions for Testflinger server."""

from datetime import datetime, timezone

from testflinger_common.enums import (
    JobEvent,
    JobState,
    TestflingerEvent,
    TestPhase,
)

_MESSAGE_TEMPLATES = {
    JobEvent.JOB_SUBMITTED: "Job submitted by user {client_id} for queue {queue_name}.",  # noqa: E501
    JobEvent.JOB_ASSIGNED: "Job assigned to agent {agent_name}.",
    JobEvent.JOB_STARTED: "Job started",
    JobEvent.JOB_PHASE_STARTED: "Phase {phase} started.",
    JobEvent.JOB_PHASE_COMPLETED: "Phase {phase} completed with exit code {status}",  # noqa: E501
    JobEvent.JOB_COMPLETED: "Job completed.",
    JobEvent.JOB_CANCELLED: "Job cancellation requested by user {client_id}.",
}


class _DefaultContext(dict):
    """Render missing placeholders instead of raising KeyError."""

    def __missing__(self, key):
        return f"<{key}>"


def format_event(event_type: TestflingerEvent, **context) -> str:
    """Interpolate the event message template with the provided context.

    :param event_type: The type of the event.
    :param context: Additional context for formatting the message.
    :return: Formatted event message based on template.
    """
    template = _MESSAGE_TEMPLATES[event_type]
    return template.format_map(_DefaultContext(context))


def build_event(
    event_type: TestflingerEvent,
    timestamp: datetime,
    detail: str = "",
    **context,
) -> dict:
    """Build an event dictionary with all relevant information.

    The event uses a formatted event message based on the event type and
    provided context.

    :param event_type: The type of the event.
    :param timestamp: The timestamp of the event.
    :param detail: Additional details for the event.
    :param context: Additional context for formatting the message.
    :return: Dictionary representing the event.
    """
    message = format_event(event_type, **context)
    return {
        "event_name": event_type,
        "timestamp": timestamp,
        "message": message,
        "detail": detail,
    }


def detect_new_result_events(
    previous_data: dict, new_data: dict
) -> list[dict]:
    """Detect job events based on the diff between previous and new results.

    Incoming POST requests can send cumulative results, so we need to determine
    which events haven't been logged yet.

    :param previous_data: The previous results data.
    :param new_data: The new results data.
    :return: List of detected new events.
    """
    timestamp = datetime.now(timezone.utc)
    return [
        *_build_phase_completed_events(previous_data, new_data, timestamp),
        *_build_job_lifecycle_events(previous_data, new_data, timestamp),
    ]


def _build_phase_completed_events(
    previous_data: dict, new_data: dict, timestamp: datetime
) -> list[dict]:
    """Get a list of phases events that are already completed.

    This compares the previous and new results data to determine
    which phases have a new `status` key reported so we can later
    log an event.

    :param previous_data: The previous results data.
    :param new_data: The new results data.
    :param timestamp: The timestamp of the event.
    :return: new phase completed events or empty list if no new events.
    """
    return [
        build_event(
            event_type=JobEvent.JOB_PHASE_COMPLETED,
            timestamp=timestamp,
            phase=phase,
            status=status,
        )
        for phase, status in new_data.get("status", {}).items()
        if phase not in previous_data.get("status", {})
    ]


def _build_job_lifecycle_events(
    previous_data: dict, new_data: dict, timestamp: datetime
) -> list[dict]:
    """Get a list of job lifecycle events.

    This compares the previous and new results data to determine
    which job lifecycle events have changed so we can later log an event.

    A job lifecycle is defined as a change in a job's state.

    :param previous_data: The previous results data.
    :param new_data: The new results data.
    :param timestamp: The timestamp of the event.
    :return: new job lifecycle events or empty list if no new events.
    """
    # Early return if there is no job_state reported yet
    new_job_state = new_data.get("job_state")
    if not new_job_state:
        return []

    previous_job_state = previous_data.get("job_state")
    # Terminal job state: log a completion event once
    if new_job_state in {"completed", "complete"}:
        if previous_job_state in {"completed", "complete"}:
            return []
        return [
            build_event(
                event_type=JobEvent.JOB_COMPLETED,
                timestamp=timestamp,
            )
        ]

    # Early return if the job state has not changed
    if (
        new_job_state not in {phase.value for phase in TestPhase}
        or new_job_state == previous_job_state
    ):
        return []

    new_events = []
    # Special handler for the first phase of a job
    if previous_job_state in (None, JobState.WAITING):
        new_events.append(
            build_event(
                event_type=JobEvent.JOB_STARTED,
                timestamp=timestamp,
                phase=new_job_state,
            )
        )
    # Any other phase change should log a phase started event
    new_events.append(
        build_event(
            event_type=JobEvent.JOB_PHASE_STARTED,
            timestamp=timestamp,
            phase=new_job_state,
        )
    )
    return new_events
