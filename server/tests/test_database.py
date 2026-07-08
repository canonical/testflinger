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

from unittest.mock import patch

import mongomock
import pytest
from mongomock.gridfs import enable_gridfs_integration

from testflinger.database import (
    DEFAULT_EXPIRATION,
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
