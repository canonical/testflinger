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
"""Unit tests for testflinger database functions."""

import datetime
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

import mongomock
import pytest
from mongomock.gridfs import enable_gridfs_integration

from testflinger.database import (
    DEFAULT_EXPIRATION,
    add_job_event,
    add_job_statistics,
    create_indexes,
    get_job_statistics_daily,
    get_job_statistics_totals,
    retrieve_file,
    save_file,
    set_agent_commanded_mode,
    update_job_results,
    upsert_agent_document,
)

# Enable GridFS support once for all tests in this module.
enable_gridfs_integration()


@pytest.mark.parametrize("state", ["waiting", "provision", "$custom", None])
@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_update_job_results_preserves_preimage_and_payload(mock_mongo, state):
    """Return the pre-image without mutating input or evaluating its values."""
    job_id = str(uuid4())
    initial_time = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    next_time = initial_time + datetime.timedelta(seconds=1)
    mock_mongo.db.jobs.insert_one(
        {
            "job_id": job_id,
            "result_data": {
                "job_state": "waiting",
                "job_state_changed_at": initial_time,
            },
        }
    )
    before = mock_mongo.db.jobs.find_one({"job_id": job_id})["result_data"]
    payload = {
        "device_info": {
            "serial": "$result_data.job_state",
            "data": ["$$ROOT"],
        },
        "job_state_changed_at": "spoofed",
    }
    if state is not None:
        payload["job_state"] = state
    original_payload = deepcopy(payload)

    with patch(
        "testflinger.database._now",
        return_value=next_time.replace(tzinfo=None),
    ):
        previous = update_job_results(job_id, payload)

    assert previous == before
    assert payload == original_payload
    stored = mock_mongo.db.jobs.find_one({"job_id": job_id})["result_data"]
    assert stored["device_info"] == payload["device_info"]
    assert stored["job_state"] == (state if state is not None else "waiting")
    expected_time = (
        next_time if state not in (None, "waiting") else initial_time
    )
    assert stored["job_state_changed_at"] == expected_time.replace(tzinfo=None)
    assert update_job_results(job_id, payload) == stored
    assert (
        mock_mongo.db.jobs.find_one({"job_id": job_id})["result_data"]
        == stored
    )


@pytest.mark.parametrize("payload", [{}, {"job_state_changed_at": "spoofed"}])
@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_update_job_results_noop(mock_mongo, payload):
    """Empty or timestamp-only updates preserve results and missing jobs."""
    job_id = str(uuid4())
    assert update_job_results(job_id, payload) == {}
    assert mock_mongo.db.jobs.count_documents({}) == 0
    before = {"job_state": "waiting"}
    mock_mongo.db.jobs.insert_one({"job_id": job_id, "result_data": before})
    assert update_job_results(job_id, payload) == before
    assert (
        mock_mongo.db.jobs.find_one({"job_id": job_id})["result_data"]
        == before
    )


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_save_file_stored_filename(mock_mongo):
    """Test save_file references the filename in the fs.files collection."""
    save_file(b"hello world", "hello.txt")

    stored = mock_mongo.db["fs.files"].find_one({"filename": "hello.txt"})
    assert stored is not None


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_save_file_as_chunks(mock_mongo):
    """Test save_file stores data as chunks with same uploadDate as file."""
    save_file(b"hello world", "hello.txt")

    file_doc = mock_mongo.db["fs.files"].find_one({"filename": "hello.txt"})

    file_id = file_doc["_id"]
    chunks = list(mock_mongo.db["fs.chunks"].find({"files_id": file_id}))
    assert chunks, "Expected at least one GridFS chunk document"
    for chunk in chunks:
        assert "uploadDate" in chunk
        assert chunk["uploadDate"] == file_doc["uploadDate"]


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_retrieve_file_returns_stored_content(mock_mongo):
    """Test retrieve_file returns the content stored with save_file."""
    content = b"hello world"
    save_file(content, "hello.txt")
    result = retrieve_file("hello.txt")
    assert result.read() == content


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_retrieve_file_raises_for_missing_file(mock_mongo):
    """Test retrieve_file raises FileNotFoundError for a non-existent file."""
    with pytest.raises(FileNotFoundError):
        retrieve_file("fake.txt")


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_create_indexes_gridfs_collections(mock_mongo):
    """Test TTL indexes are created on fs.chunks and fs.files collections."""
    # exclude compound indexes that are not relevant for gridFS
    # as those are not supported by mongomock
    with (
        patch.object(mock_mongo.db.jobs, "create_index"),
        patch.object(mock_mongo.db.logs, "create_index"),
    ):
        create_indexes()

    chunks_indexes = mock_mongo.db["fs.chunks"].index_information()
    files_indexes = mock_mongo.db["fs.files"].index_information()

    # Validate TTL index exists and has the expected expiry.
    chunks_ttl = next(
        (
            info
            for info in chunks_indexes.values()
            if info.get("key") == [("uploadDate", 1)]
        ),
        None,
    )
    files_ttl = next(
        (
            info
            for info in files_indexes.values()
            if info.get("key") == [("uploadDate", 1)]
        ),
        None,
    )
    assert chunks_ttl is not None
    assert chunks_ttl.get("expireAfterSeconds") == DEFAULT_EXPIRATION
    assert files_ttl is not None
    assert files_ttl.get("expireAfterSeconds") == DEFAULT_EXPIRATION


def _make_event(
    event: str, message: str, timestamp: datetime.datetime
) -> dict:
    """Build a minimal event dict as produced by events.build_event.
    This is using a string for the event_name instead of the enum for
    test simplicity.
    """
    return {
        "event_name": event,
        "timestamp": timestamp,
        "message": message,
        "detail": "",
    }


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_add_job_event(mock_mongo):
    """Test add_job_event stores the event in the jobs_events collection."""
    timestamp = datetime.datetime.now(datetime.timezone.utc)
    event = _make_event("job_submitted", "Job submitted", timestamp)
    job_id = str(uuid4())
    add_job_event(job_id=job_id, event=event)

    doc = mock_mongo.db.jobs_events.find_one({"job_id": job_id})
    assert doc is not None
    assert len(doc["events"]) == 1
    stored_data = doc["events"][0]
    assert stored_data["event_name"] == "job_submitted"
    assert stored_data["message"] == "Job submitted"
    # updated_at must be set for the TTL index
    assert "updated_at" in doc


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_new_job_events_preserve_insertion_order(mock_mongo):
    """Test new events are appended in insertion (oldest-first) order."""
    job_id = str(uuid4())
    timestamp = datetime.datetime(
        2026, 1, 1, 12, 0, tzinfo=datetime.timezone.utc
    )
    # timestamp is fixed for test simplicity and for validating insertion order
    events = [
        _make_event("job_submitted", "Job submitted", timestamp),
        _make_event("job_started", "Job started", timestamp),
        _make_event("job_completed", "Job completed", timestamp),
    ]

    for event in events:
        add_job_event(job_id=job_id, event=event)

    doc = mock_mongo.db.jobs_events.find_one({"job_id": job_id})
    stored_events = doc["events"]
    assert len(stored_events) == 3
    # strip tz info before comparison as mongomock stores datetime in naive UTC
    normalized_expected = [
        {**evt, "timestamp": evt["timestamp"].replace(tzinfo=None)}
        for evt in events
    ]
    assert stored_events == normalized_expected


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_set_agent_mode_stamps_change_when_mode_differs(mock_mongo):
    """A changed commanded_mode stamps commanded_mode_changed_at and _by."""
    mock_mongo.db.agents.insert_one(
        {"name": "agent1", "commanded_mode": {"value": "online"}}
    )

    set_agent_commanded_mode(
        "agent1", "offline", "downtime", "admin@example.com"
    )

    record = mock_mongo.db.agents.find_one({"name": "agent1"})
    assert record["commanded_mode"]["value"] == "offline"
    assert record["commanded_mode"]["comment"] == "downtime"
    assert record["commanded_mode"]["changed_by"] == "admin@example.com"
    assert record["commanded_mode"]["changed_at"] is not None
    assert record["updated_at"] is not None


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_set_agent_mode_no_stamp_when_mode_unchanged(mock_mongo):
    """An unchanged commanded_mode updates timestamp but not attribution."""
    mock_mongo.db.agents.insert_one(
        {"name": "agent1", "commanded_mode": {"value": "online"}}
    )

    set_agent_commanded_mode("agent1", "online", "", "admin@example.com")

    record = mock_mongo.db.agents.find_one({"name": "agent1"})
    assert record["commanded_mode"]["value"] == "online"
    assert "changed_by" not in record["commanded_mode"]
    assert "changed_at" not in record["commanded_mode"]
    assert record["commanded_mode"]["comment"] == ""
    assert record["updated_at"] is not None


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_set_agent_mode_creates_and_stamps_new_agent(mock_mongo):
    """A first-time agent is upserted with its initial commanded_mode
    stamped.
    """
    set_agent_commanded_mode(
        "newagent", "offline", "downtime", "admin@example.com"
    )

    record = mock_mongo.db.agents.find_one({"name": "newagent"})
    assert record is not None
    assert record["commanded_mode"]["value"] == "offline"
    assert record["commanded_mode"]["comment"] == "downtime"
    assert record["commanded_mode"]["changed_by"] == "admin@example.com"
    assert record["commanded_mode"]["changed_at"] is not None


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_upsert_agent_document_stamps_state_change(mock_mongo):
    """A state transition records its own timestamp."""
    timestamp = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    mock_mongo.db.agents.insert_one(
        {
            "name": "agent1",
            "mode": {"value": "online"},
            "state": {"value": "waiting"},
        }
    )

    upsert_agent_document(
        "agent1",
        {"state": "reserve", "updated_at": timestamp},
        [],
        changed_by="agent1",
    )

    record = mock_mongo.db.agents.find_one({"name": "agent1"})
    assert record["state"]["changed_at"] == timestamp.replace(tzinfo=None)


@pytest.mark.parametrize(
    "exception",
    [
        mongomock.OperationFailure("Operation failure"),
        mongomock.DuplicateKeyError("Duplicate key error"),
    ],
)
@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_add_job_event_does_not_raise_on_exception(mock_mongo, exception):
    """Test add_job_event doesn't raise an exception on MongoDB errors."""
    job_id = str(uuid4())
    timestamp = datetime.datetime.now(datetime.timezone.utc)
    event = _make_event("job_submitted", "Job submitted", timestamp)

    # Patch the mongo client to raise the specified exception
    with patch(
        "testflinger.database.mongo.db.jobs_events.update_one",
        side_effect=exception,
    ):
        add_job_event(job_id=job_id, event=event)

    doc = mock_mongo.db.jobs_events.find_one({"job_id": job_id})
    # The document should not be created due to the exception
    assert doc is None


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_add_job_statistics_adds_new_document(mock_mongo):
    """Test add_job_statistics adds a new document if none exists."""
    job_id = str(uuid4())
    statistics = {"queue": "test_queue", "submitted_by": "alice"}

    add_job_statistics(job_id, statistics)

    doc = mock_mongo.db.job_statistics.find_one({"job_id": job_id})
    assert doc is not None
    assert doc["job_id"] == job_id
    assert doc["queue"] == "test_queue"
    assert doc["submitted_by"] == "alice"


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_add_job_statistics_does_not_overwrite_existing(mock_mongo):
    """Test do not overwrite existing statistics when adding new statistics."""
    job_id = str(uuid4())
    statistics = {"queue": "test_queue", "submitted_by": "alice"}

    add_job_statistics(job_id, statistics)

    # Call again with new statistics
    # tags could come from a different source so this should be added to doc
    # submitted_by should remain unchanged since it was already set
    new_statistics = {"tags": ["tag1", "tag2"], "submitted_by": "bob"}
    add_job_statistics(job_id, new_statistics)

    doc = mock_mongo.db.job_statistics.find_one({"job_id": job_id})
    assert doc is not None
    # The original statistics should remain unchanged
    assert doc["queue"] == "test_queue"
    assert doc["submitted_by"] == "alice"
    # The new statistics should be added to the document
    assert doc["tags"] == ["tag1", "tag2"]


@pytest.mark.parametrize(
    "exception",
    [
        mongomock.OperationFailure("Operation failure"),
        mongomock.DuplicateKeyError("Duplicate key error"),
    ],
)
@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_add_job_statistics_does_not_raise_on_exception(mock_mongo, exception):
    """Test add_job_statistics doesn't raise an exception on MongoDB errors."""
    job_id = str(uuid4())
    statistics = {"queue": "test_queue", "submitted_by": "alice"}

    # Patch the mongo client to raise the specified exception
    with patch(
        "testflinger.database.mongo.db.job_statistics.update_one",
        side_effect=exception,
    ):
        add_job_statistics(job_id=job_id, statistics=statistics)

    doc = mock_mongo.db.job_statistics.find_one({"job_id": job_id})
    # The document should not be created due to the exception
    assert doc is None


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_empty_statistic_does_not_create_document(mock_mongo):
    """Test document is not created if statistics are empty."""
    job_id = str(uuid4())
    statistics = {}

    add_job_statistics(job_id, statistics)

    doc = mock_mongo.db.job_statistics.find_one({"job_id": job_id})
    assert doc is None


@pytest.mark.parametrize(
    "func", [get_job_statistics_daily, get_job_statistics_totals]
)
def test_get_job_statistics_unsupported_group_by(func):
    """Test statistics functions raise ValueError for unsupported group_by."""
    with pytest.raises(ValueError) as exc_info:
        func(group_by="unsupported_field")

    assert "Unsupported group_by" in str(exc_info.value)


def test_statistics_group_by_totals(statistics_data):
    """Test get_job_statistics_totals groups by the correct field."""
    # Group by queue
    totals_by_queue = get_job_statistics_totals(group_by="queue")
    assert totals_by_queue == [
        {"key": "queue1", "count": 2},
        {"key": "queue2", "count": 2},
    ]

    # Group by submitted_by
    totals_by_submitter = get_job_statistics_totals(group_by="submitted_by")
    assert totals_by_submitter == [
        {"key": "user1", "count": 3},
        {"key": "user2", "count": 1},
    ]


def test_statistics_group_by_daily(statistics_data):
    """Test get_job_statistics_daily groups by the correct field."""
    # Group by queue
    daily_by_queue = get_job_statistics_daily(group_by="queue")
    assert daily_by_queue == [
        {"date": "2026-01-01", "key": "queue1", "count": 1},
        {"date": "2026-01-01", "key": "queue2", "count": 1},
        {"date": "2026-01-02", "key": "queue1", "count": 1},
        {"date": "2026-01-02", "key": "queue2", "count": 1},
    ]

    # Group by submitted_by
    daily_by_submitter = get_job_statistics_daily(group_by="submitted_by")
    assert daily_by_submitter == [
        {"date": "2026-01-01", "key": "user1", "count": 2},
        {"date": "2026-01-02", "key": "user1", "count": 1},
        {"date": "2026-01-02", "key": "user2", "count": 1},
    ]


def test_statistics_totals_start_at_range(statistics_data):
    """Test get_job_statistics_totals filters by start_at range."""
    # only jobs on/after 2026-01-02
    totals = get_job_statistics_totals(
        group_by="queue",
        start_at=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
    )
    assert totals == [
        {"key": "queue1", "count": 1},
        {"key": "queue2", "count": 1},
    ]


def test_statistics_totals_end_at_range(statistics_data):
    """Test get_job_statistics_totals filters by end_at (exclusive)."""
    # only jobs before 2026-01-02 (end bound is exclusive)
    totals = get_job_statistics_totals(
        group_by="queue",
        end_at=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
    )
    assert totals == [
        {"key": "queue1", "count": 1},
        {"key": "queue2", "count": 1},
    ]


def test_statistics_totals_date_range_both_bounds(statistics_data):
    """Test get_job_statistics_totals with both start_at and end_at."""
    # window covering only 2026-01-01 (start inclusive, end exclusive)
    totals = get_job_statistics_totals(
        group_by="submitted_by",
        start_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        end_at=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
    )
    assert totals == [{"key": "user1", "count": 2}]


def test_statistics_totals_queue_filter(statistics_data):
    """Test get_job_statistics_totals filters by queue list."""
    totals = get_job_statistics_totals(group_by="queue", queues=["queue1"])
    assert totals == [{"key": "queue1", "count": 2}]

    # a queue with no jobs yields no rows
    totals = get_job_statistics_totals(group_by="queue", queues=["fake"])
    assert totals == []


def test_statistics_totals_submitter_filter(statistics_data):
    """Test get_job_statistics_totals filters by submitter list."""
    totals = get_job_statistics_totals(
        group_by="submitted_by", submitters=["user1"]
    )
    assert totals == [{"key": "user1", "count": 3}]


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_statistics_empty_collection(mock_mongo):
    """Test statistics functions return empty lists on an empty collection."""
    assert get_job_statistics_totals(group_by="queue") == []
    assert get_job_statistics_daily(group_by="queue") == []


def test_statistics_combined_filters(statistics_data):
    """Test date range combined with queue filter."""
    # queue1 jobs on/after 2026-01-02: only the user2 job qualifies
    totals = get_job_statistics_totals(
        group_by="submitted_by",
        start_at=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        queues=["queue1"],
    )
    assert totals == [{"key": "user2", "count": 1}]


# ---------------------------------------------------------------------------
# upsert_agent_document: restart and commanded_mode logic
# ---------------------------------------------------------------------------


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_agent_restart_preserves_current_mode_when_no_command_pending(
    mock_mongo,
):
    """When agent reports restart without pending command, save current mode.

    Scenario:
    1. Agent is online
    2. Agent reports mode=restart (no commanded_mode set)
    3. Server should save current mode to commanded_mode for restoration
    """
    timestamp = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    mock_mongo.db.agents.insert_one(
        {
            "name": "agent1",
            "mode": {"value": "online"},
            "state": {"value": "waiting"},
        }
    )

    # Agent reports restart without pending command
    # V2 API sends mode as nested dict: {"value": "restart", ...}
    upsert_agent_document(
        "agent1",
        {"mode": {"value": "restart"}, "updated_at": timestamp},
        [],
        changed_by="agent1",
    )

    record = mock_mongo.db.agents.find_one({"name": "agent1"})
    # Mode should be restart
    assert record["mode"]["value"] == "restart"
    # commanded_mode should be set to the previous mode (online)
    assert record["commanded_mode"]["value"] == "online"
    assert record["commanded_mode"]["changed_at"] == timestamp.replace(
        tzinfo=None
    )


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_agent_restart_preserves_pending_command(mock_mongo):
    """When agent reports restart with pending command, preserve it.

    Scenario:
    1. Admin commanded agent to restart
    2. Agent reports mode=restart
    3. Server should preserve the commanded_mode=restart (don't overwrite)
    """
    timestamp = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    mock_mongo.db.agents.insert_one(
        {
            "name": "agent1",
            "mode": {"value": "online"},
            "commanded_mode": {"value": "restart"},
        }
    )

    # Agent reports restart (acknowledging the command)
    upsert_agent_document(
        "agent1",
        {"mode": {"value": "restart"}, "updated_at": timestamp},
        [],
        changed_by="agent1",
    )

    record = mock_mongo.db.agents.find_one({"name": "agent1"})
    # Mode should be restart
    assert record["mode"]["value"] == "restart"
    # commanded_mode should still be restart (not overwritten)
    assert record["commanded_mode"]["value"] == "restart"


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_agent_acks_commanded_mode(mock_mongo):
    """When agent reports mode matching commanded_mode, clear command.

    Scenario:
    1. Admin commanded agent to offline
    2. Agent reports mode=offline
    3. Server should clear commanded_mode (ack received)
    """
    timestamp = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    mock_mongo.db.agents.insert_one(
        {
            "name": "agent1",
            "mode": {"value": "online"},
            "commanded_mode": {"value": "offline"},
        }
    )

    # Agent reports adopting the commanded mode
    unset_list = []
    upsert_agent_document(
        "agent1",
        {"mode": {"value": "offline"}, "updated_at": timestamp},
        unset_list,
        changed_by="agent1",
    )

    record = mock_mongo.db.agents.find_one({"name": "agent1"})
    # Mode should be offline
    assert record["mode"]["value"] == "offline"
    # commanded_mode should be unset (removed from database)
    assert "commanded_mode" not in record or unset_list == ["commanded_mode"]


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_agent_restart_without_current_mode_does_not_set_commanded_mode(
    mock_mongo,
):
    """When agent reports restart but has no current mode, don't set command.

    Scenario:
    1. New agent (no mode in database)
    2. Agent reports mode=restart
    3. Server should NOT set commanded_mode (nothing to preserve)
    """
    timestamp = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    # New agent, no existing record
    # After upgrade, agent record exists but mode doesn't

    mock_mongo.db.agents.insert_one({"name": "agent1"})

    # Agent reports restart (but we have no current mode to preserve)
    upsert_agent_document(
        "agent1",
        {"mode": {"value": "restart"}, "updated_at": timestamp},
        [],
        changed_by="agent1",
    )

    record = mock_mongo.db.agents.find_one({"name": "agent1"})
    # Mode should be restart
    assert record["mode"]["value"] == "restart"
    # commanded_mode should NOT be set (nothing to preserve)
    assert "commanded_mode" not in record


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_agent_reports_different_mode_preserves_commanded_mode(mock_mongo):
    """When agent reports different mode than commanded, preserve command.

    Scenario:
    1. Admin commanded agent to maintenance
    2. Agent reports mode=online (not yet adopted command)
    3. Server should preserve commanded_mode (for next cycle)
    """
    timestamp = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    mock_mongo.db.agents.insert_one(
        {
            "name": "agent1",
            "mode": {"value": "online"},
            "commanded_mode": {"value": "maintenance"},
        }
    )

    # Agent reports online (hasn't adopted maintenance yet)
    unset_list = []
    upsert_agent_document(
        "agent1",
        {"mode": {"value": "online"}, "updated_at": timestamp},
        unset_list,
        changed_by="agent1",
    )

    record = mock_mongo.db.agents.find_one({"name": "agent1"})
    # Mode should be online
    assert record["mode"]["value"] == "online"
    # commanded_mode should still be maintenance (preserved)
    assert record["commanded_mode"]["value"] == "maintenance"
    # Should NOT be in unset list
    assert "commanded_mode" not in unset_list
