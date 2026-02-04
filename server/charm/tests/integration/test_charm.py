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
"""Integration tests for Testflinger Juju charm."""

from pathlib import Path

import jubilant

from .helpers import APP_NAME, METADATA, MONGODB_CHARM, app_is_up, retry

DEFAULT_HTTP_PORT = 5000


def test_deploy(charm_path: Path, juju: jubilant.Juju):
    """Deploy the charm under test.

    Testflinger charm requires a mongodb_client relation to be established,
    so we deploy a mongodb-k8s charm alongside it.
    """
    # Deploy the testflinger charm
    resources = {
        "testflinger-image": METADATA["resources"]["testflinger-image"][
            "upstream-source"
        ],
    }
    juju.deploy(charm_path.resolve(), app=APP_NAME, resources=resources)

    # Deploy the mongodb-k8s charm
    juju.deploy(MONGODB_CHARM, channel="6/stable", trust=True)

    # Establish the mongodb_client relation
    juju.integrate(APP_NAME, MONGODB_CHARM)
    juju.wait(jubilant.all_active)


@retry(retry_num=10, retry_sleep_sec=3)
def test_application_is_up(juju: jubilant.Juju):
    """Test that the deployed application is up and responding."""
    ip = juju.status().apps[APP_NAME].units[f"{APP_NAME}/0"].address
    base_url = f"http://{ip}:{DEFAULT_HTTP_PORT}"
    assert app_is_up(base_url)
