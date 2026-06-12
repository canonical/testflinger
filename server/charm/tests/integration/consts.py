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
"""Constants for integration tests."""

from pathlib import Path

import yaml

# Charms naming constants
HAPROXY_CHARM = "haproxy"
SELFSIGNED_CHARM = "self-signed-certificates"
INGRESS_CHARM = "ingress-configurator"
MONGODB_CHARM = "mongodb-k8s"
NGINX_INGRESS_CHARM = "nginx-ingress-integrator"

# Testflinger application constants
METADATA = yaml.safe_load(Path("charmcraft.yaml").read_text(encoding="utf-8"))
APP_NAME = METADATA["name"]
UPSTREAM_SOURCE = METADATA["resources"]["testflinger-image"]["upstream-source"]
DEFAULT_EXTERNAL_HOSTNAME = "testflinger.local"
DEFAULT_HTTP_PORT = 5000

# Ingress related constants
HAPROXY_EXTERNAL_HOSTNAME = "fqdn.example"
INGRESS_NAME = "ingress"
