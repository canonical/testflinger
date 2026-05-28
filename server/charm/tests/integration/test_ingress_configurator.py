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
import pytest_jubilant
import requests

from .consts import (
    APP_NAME,
    DEFAULT_EXTERNAL_HOSTNAME,
    HAPROXY_CHARM,
    HAPROXY_EXTERNAL_HOSTNAME,
    INGRESS_CHARM,
    INGRESS_NAME,
    MONGODB_CHARM,
    SELFSIGNED_CHARM,
    UPSTREAM_SOURCE,
)
from .helpers import DNSResolverHTTPAdapter, app_is_up, get_haproxy_ip, retry

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def machine_juju(juju_factory: pytest_jubilant.JujuFactory):
    """Juju instance for the machine model hosting haproxy."""
    yield juju_factory.get_juju(suffix="machine")


@pytest.mark.juju_setup
def test_deploy(
    charm_path: Path, juju: jubilant.Juju, machine_juju: jubilant.Juju
):
    """Test deploying the charm under test with haproxy ingress via CMR."""
    # First deploy haproxy in the machine model
    machine_juju.deploy(HAPROXY_CHARM, channel="2.8/edge", trust=True)
    machine_juju.deploy(SELFSIGNED_CHARM)
    machine_juju.config(
        HAPROXY_CHARM, {"external-hostname": HAPROXY_EXTERNAL_HOSTNAME}
    )
    machine_juju.integrate(HAPROXY_CHARM, f"{SELFSIGNED_CHARM}:certificates")

    logger.info("Waiting for machine model to be active")
    machine_juju.wait(jubilant.all_active)

    # Offer haproxy-route endpoint from machine model
    machine_juju.cli(
        "offer",
        f"{HAPROXY_CHARM}:haproxy-route",
        HAPROXY_CHARM,
    )

    # Consume the offered haproxy route in the testflinger model (cross-model)
    juju.cli("consume", f"admin/{machine_juju.model}.{HAPROXY_CHARM}")

    # Deploy the testflinger charm
    resources = {
        "testflinger-image": UPSTREAM_SOURCE,
    }
    juju.deploy(charm_path.resolve(), app=APP_NAME, resources=resources)

    # Deploy the mongodb-k8s charm
    juju.deploy(MONGODB_CHARM, channel="6/stable", trust=True)
    juju.integrate(
        f"{APP_NAME}:mongodb_client",
        f"{MONGODB_CHARM}:database",
    )
    juju.integrate(
        f"{APP_NAME}:mongodb_keyvault",
        f"{MONGODB_CHARM}:database",
    )
    juju.wait(jubilant.all_active)

    # Deploy ingress-configurator with the Testflinger hostname
    juju.deploy(
        INGRESS_CHARM,
        app=INGRESS_NAME,
        channel="latest/edge",
        config={"hostname": DEFAULT_EXTERNAL_HOSTNAME},
        trust=True,
    )

    # Integrate consumed haproxy with ingress-configurator (cross-model)
    logger.info("Integrating haproxy (CMR) with ingress-configurator")
    juju.integrate(f"{HAPROXY_CHARM}:haproxy-route", f"{INGRESS_NAME}:ingress")
    juju.wait(jubilant.all_active)

    # Integrate testflinger with ingress
    logger.info("Integrating testflinger with ingress")
    juju.integrate(f"{APP_NAME}:ingress", f"{INGRESS_NAME}:ingress")
    logger.info("Waiting for integration to complete")
    juju.wait(jubilant.all_active)


@retry(retry_num=5, retry_sleep_sec=10)
def test_ingress_is_up_default_hostname(
    juju: jubilant.Juju, machine_juju: jubilant.Juju
):
    """Test that the deployed application is up and responding via ingress.

    External hostname is configured in Ingress Configurator charm config.
    Traffic flows through haproxy (machine model) via cross-model relation.
    """
    ingress_ip = get_haproxy_ip(machine_juju)
    logger.info("HAProxy IP: %s", ingress_ip)
    session = requests.Session()
    session.mount(
        "https://",
        DNSResolverHTTPAdapter(DEFAULT_EXTERNAL_HOSTNAME, ingress_ip),
    )
    base_url = f"https://{DEFAULT_EXTERNAL_HOSTNAME}"
    result = app_is_up(base_url, session=session)
    logger.info("Connectivity test: %s", "PASS" if result else "FAIL")
    assert result


@pytest.mark.juju_teardown
def test_destroy(juju: jubilant.Juju, machine_juju: jubilant.Juju):
    """Tear down the charm under test."""
    juju.remove_application(APP_NAME)
    juju.remove_application(MONGODB_CHARM)
    juju.remove_application(INGRESS_NAME)
    # Remove the consumed SAAS app from the K8s model
    juju.cli("remove-saas", HAPROXY_CHARM)
    # Remove the offer and apps from the machine model
    machine_juju.cli(
        "remove-offer",
        f"admin/{machine_juju.model}.{HAPROXY_CHARM}",
        "--force",
    )
    machine_juju.remove_application(HAPROXY_CHARM)
    machine_juju.remove_application(SELFSIGNED_CHARM)
