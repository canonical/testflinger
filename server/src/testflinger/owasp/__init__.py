# Copyright (C) 2026 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Stub to allow for use of Otel later by overloading OWASPLogger."""

import importlib
import os

from owasp_logger import OWASPLogger as TrueOWASPLogger

# Note: it is anticipated that OTEL logging may happen in the future and so if
#       and when it does, it should be able to be slipped into place here
#       without the need to change how logging is done everywhere else.

TESTFLINGER_APP_ID = "com.canonical.testflinger"


class OWASPLogger(TrueOWASPLogger):
    """Wraps the given logger in an OWASP logger which provides a consistent
    app name.
    """

    def __init__(self, *args, **kwargs):
        """Initialize OWASP logger with testflinger app ID."""
        kwargs["appid"] = TESTFLINGER_APP_ID
        super().__init__(*args, **kwargs)

    @staticmethod
    def get_request_metadata(request) -> dict:
        """
        Extract OWASP metadata from Flask request context.

        :param request: Flask request object
        :return: Dictionary with OWASP metadata fields
        """
        try:
            port = int(request.environ.get("SERVER_PORT", 5000))
        except (ValueError, TypeError):
            port = 5000

        return {
            "source_ip": request.remote_addr,
            "host_ip": request.host.split(":")[0],
            "hostname": os.environ.get("HOSTNAME"),
            "protocol": request.scheme,
            "port": port,
            "request_uri": request.path,
            "request_method": request.method,
        }


class OTELResource:
    """OTEL resource for tracing context."""

    def __init__(self, g, request):
        """Initialize OTEL resource from Flask context."""
        try:
            version = importlib.metadata.version("testflinger")
        except importlib.metadata.PackageNotFoundError:
            version = "devel"

        self._dict = {
            "HOSTNAME": os.environ.get("HOSTNAME"),
            "MONGODB_HOST": os.environ.get("MONGODB_HOST"),
            "OIDC_PROVIDER_ISSUER": os.environ.get("OIDC_PROVIDER_ISSUER"),
            "SERVER_SOFTWARE": os.environ.get("SERVER_SOFTWARE"),
            "TESTFLINGER_VERSION": version,
        }

    def __repr__(self):
        """Return string representation of resource dict."""
        return str(self._dict)
