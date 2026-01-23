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
"""Ingress Integration tests for Testflinger Juju charm."""

import re
from pathlib import Path

import jubilant
import requests

from .helpers import (
    APP_NAME,
    METADATA,
    MONGODB_CHARM,
    DNSResolverHTTPAdapter,
    app_is_up,
    retry,
)

NGINX_INGRESS_CHARM = "nginx-ingress-integrator"
DEFAULT_EXTERNAL_HOSTNAME = "testflinger.local"
INGRESS_NAME = "ingress"


def test_deploy(charm_path: Path, juju: jubilant.Juju):
    """Test deploying the charm under test with ingress relation."""
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

    # Deploy the nginx-ingress-integrator charm
    juju.deploy(
        NGINX_INGRESS_CHARM,
        app=INGRESS_NAME,
        channel="latest/stable",
        trust=True,
    )

    # Establish the nginx-route relation
    juju.integrate(APP_NAME, INGRESS_NAME)
    juju.wait(jubilant.all_active)


@retry(retry_num=5, retry_sleep_sec=5)
def test_ingress_is_up(juju: jubilant.Juju):
    """Test that the deployed application is up and responding via ingress."""
    # For nginx-ingress-integrator, the ingress IP is in the app status message
    status_message = juju.status().apps[INGRESS_NAME].app_status.message
    match = re.search(r"Ingress IP\(s\): ([\d.]+)", status_message)
    assert match, f"Could not find ingress IP in status: {status_message}"

    ingress_ip = match.group(1)
    session = requests.Session()
    session.mount(
        "http://",
        DNSResolverHTTPAdapter(DEFAULT_EXTERNAL_HOSTNAME, ingress_ip),
    )
    session.mount(
        "https://",
        DNSResolverHTTPAdapter(DEFAULT_EXTERNAL_HOSTNAME, ingress_ip),
    )
    base_url = f"http://{DEFAULT_EXTERNAL_HOSTNAME}"
    assert app_is_up(base_url, session=session)
