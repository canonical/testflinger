# Copyright (C) 2016-2022 Canonical
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
"""Unit tests for Testflinger flask app."""

import pytest

from testflinger.application import create_flask_app


def test_default_config(testapp):
    """Test default config settings."""
    app = testapp
    assert app.config.get("PROPAGATE_EXCEPTIONS") is True


def test_setup_mongo_fails_without_config():
    """Ensure setup_mongo fails without config."""
    with pytest.raises(SystemExit) as exc:
        create_flask_app()
    assert exc.value.code == "No MongoDB URI configured!"
