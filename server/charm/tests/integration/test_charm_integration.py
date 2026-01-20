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
import yaml

METADATA = yaml.safe_load(Path("charmcraft.yaml").read_text(encoding="utf-8"))
APP_NAME = METADATA["name"]
MONGODB_CHARM = "mongodb-k8s"
NGINX_INGRESS_CHARM = "nginx-ingress-integrator"


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


def test_relate_ingress(juju: jubilant.Juju):
    """Relate the charm under test to the nginx ingress integrator."""
    # Deploy the nginx-ingress-integrator charm
    juju.deploy(NGINX_INGRESS_CHARM, channel="latest/stable", trust=True)

    # Establish the nginx-route relation
    juju.integrate(APP_NAME, NGINX_INGRESS_CHARM)
    juju.wait(jubilant.all_active)
