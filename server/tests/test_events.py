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
"""Unit tests for testflinger events functions."""

import pytest
from testflinger_common.enums import JobEvent, JobState

from testflinger.events import detect_new_result_events


def _event_names(events: list[dict]) -> list[str]:
    """Extract event_name values from a list of event dicts."""
    return [event["event_name"] for event in events]


def test_first_phase_transition_emits_job_started():
    """Test transitioning from explicit "waiting" state emits JOB_STARTED."""
    previous_data = {"job_state": JobState.WAITING}
    new_data = {"job_state": JobState.SETUP}

    events = detect_new_result_events(previous_data, new_data)

    assert set(_event_names(events)) == {
        JobEvent.JOB_STARTED,
        JobEvent.JOB_PHASE_STARTED,
    }


def test_subsequent_phase_transition_emits_only_phase_started():
    """Test a phase-to-phase transition only emits JOB_PHASE_STARTED."""
    previous_data = {"job_state": JobState.SETUP}
    new_data = {"job_state": JobState.PROVISION}

    events = detect_new_result_events(previous_data, new_data)

    assert _event_names(events) == [JobEvent.JOB_PHASE_STARTED]


def test_same_job_state_emits_no_events():
    """Test re-posting the same job_state does not emit duplicate events."""
    previous_data = {"job_state": JobState.PROVISION}
    new_data = {"job_state": JobState.PROVISION}

    events = detect_new_result_events(previous_data, new_data)

    assert events == []


def test_new_status_key_emits_phase_completed():
    """Test a newly-reported phase status emits JOB_PHASE_COMPLETED."""
    previous_data = {}
    new_data = {"status": {JobState.SETUP: 0}}

    events = detect_new_result_events(previous_data, new_data)

    assert len(events) == 1
    assert events[0]["event_name"] == JobEvent.JOB_PHASE_COMPLETED
    assert JobState.SETUP.value in events[0]["message"]


def test_repeated_status_key_emits_no_duplicate_event():
    """Test re-posting the same phase status emits no duplicate event."""
    previous_data = {"status": {JobState.SETUP: 0}}
    new_data = {"status": {JobState.SETUP: 0}}

    events = detect_new_result_events(previous_data, new_data)

    assert events == []


def test_multiple_new_status_keys_emit_multiple_events():
    """Test multiple new phase statuses in one payload each emit an event."""
    previous_data = {"status": {}}
    new_data = {"status": {JobState.SETUP: 0, JobState.PROVISION: 1}}

    events = detect_new_result_events(previous_data, new_data)

    assert len(events) == 2
    assert all(
        event["event_name"] == JobEvent.JOB_PHASE_COMPLETED for event in events
    )
    messages = [event["message"] for event in events]
    assert any(JobState.SETUP.value in message for message in messages)
    assert any(JobState.PROVISION.value in message for message in messages)


@pytest.mark.parametrize("terminal_state", (JobState.COMPLETED, "completed"))
def test_terminal_job_state_completed_emits_job_completed(terminal_state):
    """Test a terminal job_state emits JOB_COMPLETED."""
    previous_data = {"job_state": JobState.CLEANUP}
    new_data = {"job_state": terminal_state}

    events = detect_new_result_events(previous_data, new_data)

    assert _event_names(events) == [JobEvent.JOB_COMPLETED]


def test_cancelled_job_state_emits_no_events():
    """Test job_state "cancelled" emits no events from this function.

    Cancellation events are recorded separately via the job action
    endpoint, not through result posts.
    """
    previous_data = {"job_state": JobState.TEST}
    new_data = {"job_state": JobState.CANCELLED}

    events = detect_new_result_events(previous_data, new_data)

    assert events == []


def test_empty_payload_emits_no_events():
    """Test a payload with neither job_state nor status emits nothing."""
    previous_data = {"job_state": JobState.TEST, "status": {JobState.TEST: 0}}
    new_data = {"device_info": {"foo": "bar"}}

    events = detect_new_result_events(previous_data, new_data)

    assert events == []
