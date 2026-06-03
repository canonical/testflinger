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
import pytest

from .consts import APP_NAME, DEFAULT_HTTP_PORT, MONGODB_CHARM, UPSTREAM_SOURCE
from .helpers import app_is_up, retry


@pytest.mark.juju_setup
def test_deploy(charm_path: Path, k8s_juju: jubilant.Juju):
    """Deploy the charm under test.

    Testflinger charm requires a mongodb_client relation to be established,
    so we deploy a mongodb-k8s charm alongside it.
    """
    # Deploy the testflinger charm
    resources = {
        "testflinger-image": UPSTREAM_SOURCE,
    }
    k8s_juju.deploy(charm_path.resolve(), app=APP_NAME, resources=resources)

    # Deploy the mongodb-k8s charm
    k8s_juju.deploy(MONGODB_CHARM, channel="6/stable", trust=True)

    # Establish the mongodb_client and mongodb_keyvault relations
    k8s_juju.integrate(
        f"{APP_NAME}:mongodb_client", f"{MONGODB_CHARM}:database"
    )
    k8s_juju.integrate(
        f"{APP_NAME}:mongodb_keyvault", f"{MONGODB_CHARM}:database"
    )
    k8s_juju.wait(jubilant.all_active)


@retry(retry_num=10, retry_sleep_sec=3)
def test_application_is_up(k8s_juju: jubilant.Juju):
    """Test that the deployed application is up and responding."""
    ip = k8s_juju.status().apps[APP_NAME].units[f"{APP_NAME}/0"].address
    base_url = f"http://{ip}:{DEFAULT_HTTP_PORT}"
    assert app_is_up(base_url)


@pytest.mark.juju_teardown
def test_destroy(k8s_juju: jubilant.Juju):
    """Tear down the charm under test."""
    k8s_juju.remove_application(APP_NAME)
    k8s_juju.remove_application(MONGODB_CHARM)
