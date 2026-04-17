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
from typing import TypedDict

from owasp_logger import OWASPLogger as TrueOWASPLogger

# Note: it is anticipated that OTEL logging may happen in the future and so if
#       and when it does, it should be able to be slipped into place here
#       without the need to change how logging is done everywhere else.

TESTFLINGER_APP_ID = "com.canonical.testflinger"


class RequestMetadata(TypedDict, total=False):
    """Request metadata for OWASP logging."""

    source_ip: str
    host_ip: str
    hostname: str
    protocol: str
    port: int
    request_uri: str
    request_method: str


class OWASPLogger(TrueOWASPLogger):
    """Wraps the given logger in an OWASP logger which provides a consistent
    app name.
    """

    def __init__(self, *args, **kwargs):
        """Initialize OWASP logger with testflinger app ID."""
        kwargs["appid"] = TESTFLINGER_APP_ID
        super().__init__(*args, **kwargs)

    @staticmethod
    def get_request_metadata(request) -> RequestMetadata:
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


# logger.warning(pprint.pformat(request.environ))

#  'HTTP_ACCEPT_ENCODING': 'gzip, deflate',
#  'HTTP_ACCEPT_LANGUAGE': 'en-US,en;q=0.9',
#  'HTTP_CACHE_CONTROL': 'max-age=0',
#  'HTTP_CONNECTION': 'keep-alive',
#  'HTTP_DNT': '1',
#  'HTTP_HOST': '10.107.87.20:5000',
#  'HTTP_UPGRADE_INSECURE_REQUESTS': '1',
#  'HTTP_USER_AGENT': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
#                     '(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
#  'PATH_INFO': '/v1/',
#  'QUERY_STRING': '',
#  'RAW_URI': '/v1/',
#  'REMOTE_ADDR': '10.107.87.1',
#  'REMOTE_PORT': '59526',
#  'REQUEST_METHOD': 'GET',
#  'SCRIPT_NAME': '',
#  'SERVER_NAME': '0.0.0.0',
#  'SERVER_PORT': '5000',
#  'SERVER_PROTOCOL': 'HTTP/1.1',
#  'SERVER_SOFTWARE': 'gunicorn/25.0.1',
#  'werkzeug.request': <Request 'http://10.107.87.20:5000/v1/' [GET]>,
#  'wsgi.input_terminated': True,
#  'wsgi.multiprocess': False,
#  'wsgi.multithread': False,
#  'wsgi.run_once': False,
#  'wsgi.url_scheme': 'http',
#  'wsgi.version': (1, 0)}
