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

"""Tests for the rotate_mongo_secrets_key tool."""

import base64
import os

import pytest
from pymongo.encryption import ClientEncryption

from testflinger.tools.rotate_mongo_secrets_key import main, rotate_master_key

MONGO_URI = "mongodb://localhost:27017/testflinger_db"


@pytest.fixture
def mock_cipher(mocker):
    """Mock ClientEncryption to return a controlled instance."""
    cipher = mocker.Mock(spec=ClientEncryption)
    cipher.rewrap_many_data_key.return_value = mocker.Mock(
        bulk_write_result=mocker.Mock(modified_count=1)
    )
    mocker.patch(
        "testflinger.tools.rotate_mongo_secrets_key._make_cipher",
        return_value=cipher,
    )
    mocker.patch("testflinger.tools.rotate_mongo_secrets_key.MongoClient")
    return cipher


def test_rewrap_called_with_new_master_key(mock_cipher):
    """Test rewrap_many_data_key is called for both rotation phases."""
    old_key, new_key = os.urandom(96), os.urandom(96)
    rotate_master_key(
        old_master_key=old_key,
        new_master_key=new_key,
        key_vault_ns="encryption.__keyVault",
        key_vault_uri=MONGO_URI,
    )

    # Phase 1: old "local" -> "local:new" (new key)
    mock_cipher.rewrap_many_data_key.assert_any_call({}, provider="local:new")
    # Phase 2: "local:new" -> "local" (new key), restoring canonical name
    mock_cipher.rewrap_many_data_key.assert_any_call({}, provider="local")


def test_cipher_closed_on_completion(mock_cipher):
    """Test that the cipher is closed after both rotation phases."""
    rotate_master_key(
        old_master_key=os.urandom(96),
        new_master_key=os.urandom(96),
        key_vault_ns="encryption.__keyVault",
        key_vault_uri=MONGO_URI,
    )

    assert mock_cipher.close.call_count == 2


def test_prints_rotation_complete(mock_cipher, capsys):
    """Test complete message printed after successful rotation."""
    rotate_master_key(
        old_master_key=os.urandom(96),
        new_master_key=os.urandom(96),
        key_vault_ns="encryption.__keyVault",
        key_vault_uri=MONGO_URI,
    )

    assert "Rotation complete." in capsys.readouterr().out


def test_exits_when_both_keys_missing(mocker):
    """Test script exits non-zero when both key env vars are absent."""
    mocker.patch.dict("os.environ", {}, clear=True)
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0


def test_exits_when_new_key_missing(mocker):
    """Test script exits non-zero when only the new key env var is absent."""
    key = base64.b64encode(os.urandom(96)).decode()
    mocker.patch.dict(
        "os.environ",
        {"TESTFLINGER_SECRETS_MASTER_KEY": key},
        clear=True,
    )
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0


def test_calls_rotate_master_key_when_both_keys_set(mocker):
    """Test script calls rotate_master_key() when both key env vars are set."""
    old_key = base64.b64encode(os.urandom(96)).decode()
    new_key = base64.b64encode(os.urandom(96)).decode()
    mocker.patch.dict(
        "os.environ",
        {
            "TESTFLINGER_SECRETS_MASTER_KEY": old_key,
            "TESTFLINGER_SECRETS_NEW_MASTER_KEY": new_key,
        },
        clear=True,
    )
    mocker.patch(
        "testflinger.tools.rotate_mongo_secrets_key.get_mongo_uri",
        return_value=MONGO_URI,
    )
    mock_rotate = mocker.patch(
        "testflinger.tools.rotate_mongo_secrets_key.rotate_master_key"
    )

    main()

    mock_rotate.assert_called_once()
    kwargs = mock_rotate.call_args.kwargs
    assert kwargs["old_master_key"] != kwargs["new_master_key"]
    assert kwargs["key_vault_uri"] == MONGO_URI
