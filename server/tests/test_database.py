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

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import mongomock
import pytest
from mongomock.gridfs import enable_gridfs_integration

import testflinger.database as database
from testflinger.database import (
    DEFAULT_EXPIRATION,
    add_agent_event,
    create_indexes,
    get_agent_events,
    retrieve_file,
    save_file,
)

# Enable GridFS support once for all tests in this module.
enable_gridfs_integration()


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


def _make_event(event: str, message: str, timestamp: datetime) -> dict:
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
def test_add_agent_event_stores_envelope(mock_mongo):
    """Test add_agent_event stores the full event envelope and updated_at."""
    timestamp = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)
    event = _make_event("agent_offline", "Agent set to offline", timestamp)
    add_agent_event("agent1", event)

    doc = mock_mongo.db.agents_events.find_one({"agent_name": "agent1"})
    assert doc is not None
    assert len(doc["events"]) == 1
    stored = doc["events"][0]
    assert stored["event_name"] == "agent_offline"
    # mongomock (like MongoDB) returns datetimes as naive UTC
    assert stored["timestamp"] == timestamp.replace(tzinfo=None)
    assert stored["message"] == "Agent set to offline"
    assert stored["detail"] == ""
    # updated_at must be set for the TTL index
    assert "updated_at" in doc


@patch.object(database, "AGENT_EVENT_LIMIT", 3)
@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_add_agent_event_fifo_cap(mock_mongo):
    """Test the event log is capped and keeps the newest events first."""
    base = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)
    # Push 5 events with increasing timestamps (oldest first)
    for i in range(5):
        database.add_agent_event(
            "agent1",
            _make_event(
                f"event {i}",
                f"Event {i} occurred",
                base + timedelta(seconds=i),
            ),
        )

    doc = mock_mongo.db.agents_events.find_one({"agent_name": "agent1"})
    events = doc["events"]
    # The event log should be capped at 3 events
    assert len(events) == 3
    # Newest first; the two oldest (event 0, event 1) were already dropped
    messages = [evt["message"] for evt in events]
    assert messages == [
        "Event 4 occurred",
        "Event 3 occurred",
        "Event 2 occurred",
    ]


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_get_agent_events_all_and_limit(mock_mongo):
    """Test get_agent_events returns all events or a limited newest subset."""
    base = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(4):
        add_agent_event(
            "agent1",
            _make_event(
                f"event {i}",
                f"Event {i} occurred",
                base + timedelta(seconds=i),
            ),
        )

    # no limit returns all events, newest first
    all_events = get_agent_events("agent1", None)
    assert len(all_events) == 4
    # Newest first
    assert all_events[0]["message"] == "Event 3 occurred"

    # limit returns only the newest events up to the limit
    limited = get_agent_events("agent1", 2)
    assert len(limited) == 2
    assert [evt["message"] for evt in limited] == [
        "Event 3 occurred",
        "Event 2 occurred",
    ]


@patch("testflinger.database.mongo", new_callable=mongomock.MongoClient)
def test_get_agent_events_unknown_agent(mock_mongo):
    """Test get_agent_events returns an empty list for an unknown agent."""
    assert get_agent_events("nonexistent", None) == []
