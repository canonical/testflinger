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

from testflinger.database import retrieve_file, save_file

DEFAULT_EXPIRATION = 60 * 60 * 24 * 7  # 7 days in seconds

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
    mock_mongo.db["fs.chunks"].create_index(
        "uploadDate", expireAfterSeconds=DEFAULT_EXPIRATION
    )
    mock_mongo.db["fs.files"].create_index(
        "uploadDate", expireAfterSeconds=DEFAULT_EXPIRATION
    )

    chunks_indexes = mock_mongo.db["fs.chunks"].index_information()
    files_indexes = mock_mongo.db["fs.files"].index_information()

    # We expect at least the default _id index plus the TTL index on uploadDate
    assert len(chunks_indexes) > 1
    assert len(files_indexes) > 1
