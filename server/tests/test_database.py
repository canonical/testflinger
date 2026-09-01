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
from unittest.mock import patch
from uuid import uuid4

import mongomock
import pytest
from mongomock.gridfs import enable_gridfs_integration

from testflinger.database import (
    DEFAULT_EXPIRATION,
    add_job_event,
    create_indexes,
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
def test_new_job_events_sorted_by_timestamp(mock_mongo):
    """Test new jobs are appended to collection, sorted by desc timestamp."""
    job_id = str(uuid4())
    timestamps = [
        datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.timezone.utc),
        datetime.datetime(2026, 1, 1, 12, 5, tzinfo=datetime.timezone.utc),
        datetime.datetime(2026, 1, 1, 12, 10, tzinfo=datetime.timezone.utc),
    ]
    events = [
        _make_event("job_submitted", "Job submitted", timestamps[0]),
        _make_event("job_started", "Job started", timestamps[1]),
        _make_event("job_completed", "Job completed", timestamps[2]),
    ]

    for event in events:
        add_job_event(job_id=job_id, event=event)

    doc = mock_mongo.db.jobs_events.find_one({"job_id": job_id})
    stored_events = doc["events"]
    assert len(stored_events) == 3
    # We need to sort the expected events by timestamp to match the db ordering
    expected_events = sorted(
        events, key=lambda evt: evt["timestamp"], reverse=True
    )
    # strip tz info before comparison as mongomock stores datetime in naive UTC
    normalized_expected = [
        {**evt, "timestamp": evt["timestamp"].replace(tzinfo=None)}
        for evt in expected_events
    ]
    assert stored_events == normalized_expected
