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

import logging
from pathlib import Path

import jubilant
import pytest
import requests

from .helpers import (
    APP_NAME,
    METADATA,
    MONGODB_CHARM,
    DNSResolverHTTPAdapter,
    app_is_up,
    get_k8s_ingress_object_ip,
    retry,
)

logger = logging.getLogger(__name__)

INGRESS_CHARM = "ingress-configurator"
DEFAULT_EXTERNAL_HOSTNAME = "testflinger.local"
INGRESS_NAME = "ingress"


@pytest.mark.juju_setup
def test_deploy(charm_path: Path, juju: jubilant.Juju):
    """Test deploying the charm under test with traefik ingress relation."""
    # Deploy the testflinger charm
    resources = {
        "testflinger-image": METADATA["resources"]["testflinger-image"][
            "upstream-source"
        ],
    }
    juju.deploy(
        charm_path.resolve(), app=APP_NAME, resources=resources
    )

    # Deploy the mongodb-k8s charm
    juju.deploy(MONGODB_CHARM, channel="6/stable", trust=True)

    # Establish the mongodb_client and mongodb_keyvault relations
    juju.integrate(f"{APP_NAME}:mongodb_client", f"{MONGODB_CHARM}:database")
    juju.integrate(f"{APP_NAME}:mongodb_keyvault", f"{MONGODB_CHARM}:database")
    juju.wait(jubilant.all_active)

    # Set default external hostname in the Ingress Configurator charm config
    config = {"external_hostname": DEFAULT_EXTERNAL_HOSTNAME}
    # Deploy the traefik-k8s charm
    juju.deploy(
        INGRESS_CHARM,
        app=INGRESS_NAME,
        channel="latest/edge",
        config=config,
        trust=True,
    )
    # Wait for ingress-configurator to be active
    logger.info("Waiting for ingress-configurator to be active")
    juju.wait(jubilant.all_active)

    # Establish the ingress relation
    logger.info("Integrating ingress relation")
    juju.integrate(
        f"{APP_NAME}:ingress", f"{INGRESS_NAME}:ingress"
    )
    logger.info("Waiting for integration to complete")
    juju.wait(jubilant.all_active)


@retry(retry_num=5, retry_sleep_sec=10)
def test_ingress_is_up_default_hostname(juju: jubilant.Juju):
    """Test that the deployed application is up and responding via ingress.

    External hostname is configured in Ingress Configurator charm config.
    """
    model = juju.show_model()
    ingress_ip = get_k8s_ingress_object_ip(model.short_name)
    logger.info("Ingress IP: %s", ingress_ip)
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
    result = app_is_up(base_url, session=session)
    logger.info("Connectivity test: %s", "PASS" if result else "FAIL")
    assert result


@pytest.mark.juju_teardown
def test_destroy(juju: jubilant.Juju):
    """Tear down the charm under test."""
    juju.remove_application(APP_NAME)
    juju.remove_application(MONGODB_CHARM)
    juju.remove_application(INGRESS_NAME)
