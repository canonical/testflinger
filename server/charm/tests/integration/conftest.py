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
"""Fixtures for charm integration tests."""

import logging
import os
from pathlib import Path

import pytest
import pytest_jubilant

logger = logging.getLogger(__name__)

K8S_CONTROLLER = os.getenv("JUJU_K8S_CONTROLLER")
MACHINE_CONTROLLER = os.getenv("JUJU_MACHINE_CONTROLLER")


@pytest.fixture(scope="module")
def k8s_juju(juju_factory: pytest_jubilant.JujuFactory):
    """Juju instance for a model on the k8s controller."""
    if not K8S_CONTROLLER:
        pytest.fail(
            "JUJU_K8S_CONTROLLER is not set; cannot create a K8s model"
        )
    yield juju_factory.get_juju(suffix="k8s", controller=K8S_CONTROLLER)


@pytest.fixture(scope="module")
def machine_juju(juju_factory: pytest_jubilant.JujuFactory):
    """Juju instance for a model on the machine controller."""
    if not MACHINE_CONTROLLER:
        pytest.fail(
            "JUJU_MACHINE_CONTROLLER is not set; cannot create a machine model"
        )
    yield juju_factory.get_juju(
        suffix="machine", controller=MACHINE_CONTROLLER
    )


@pytest.fixture(scope="session")
def charm_path():
    """Return the path of the charm under test."""
    if "CHARM_PATH" in os.environ:
        charm_path = Path(os.environ["CHARM_PATH"])
        if not charm_path.exists():
            raise FileNotFoundError(f"Charm does not exist: {charm_path}")
        return charm_path
    charm_paths = list(Path(".").glob("*.charm"))
    if not charm_paths:
        raise FileNotFoundError("No .charm file in current directory")
    if len(charm_paths) > 1:
        path_list = ", ".join(str(p) for p in charm_paths)
        raise ValueError(
            f"More than one .charm file in current directory: {path_list}"
        )
    return charm_paths[0]
