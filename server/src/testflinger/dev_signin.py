# Copyright (C) 2026 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Development-only auto sign-in blueprint.

Enabled only when the ``TF_DEV_AUTO_SIGNIN`` env var is set to ``"1"`` AND
OIDC is configured (``current_app.oauth is not None``). When active, exposes
``POST /auth/dev-signin`` with ``email=<addr>`` in the form body, which
unconditionally creates a session as one of the well-known development
identities listed in ``DEV_SIGNIN_IDENTITIES`` and sets that identity's
role in ``client_permissions`` to the entry's declared role.

POST (not GET) because this mutates server state (session + a
``client_permissions`` row) and must not be reachable by prefetchers,
link crawlers, ``<img src>`` shenanigans, or a stray browser history
revisit. It also sidesteps reverse-proxy query-string mangling of the
``@`` in the email that GET-with-query-param variants ran into.

DO NOT enable in production. There is no credential check on the route; the
env var is the only gate.

Shortcuts are provided for at least one identity of every role because almost
every non-public view requires an authenticated session, and there is
currently no "logged in but no role" state that would let us exercise the
contributor code paths without a real session.

``devel/generate_sample_users.py`` derives both these identities and Dex's
``staticPasswords`` entries from ``devel/sample_users.py``. The stable Dex
subject lets both login paths update the same permissions record.
"""

import os
from http import HTTPStatus

from apiflask import abort
from flask import Blueprint, current_app, redirect, request, session, url_for
from testflinger_common.enums import ServerRoles

from testflinger import database
from testflinger.dev_signin_identities import DEV_SIGNIN_IDENTITIES

DEV_AUTO_SIGNIN_ENV_VAR = "TF_DEV_AUTO_SIGNIN"

dev_signin = Blueprint("dev_signin", __name__)


def dev_auto_signin_enabled() -> bool:
    """Return True if the auto sign-in route/button should be active."""
    return os.environ.get(DEV_AUTO_SIGNIN_ENV_VAR, "").strip() == "1"


def _find_identity(email: str) -> dict | None:
    """Return the allowlist entry matching ``email``, or None."""
    for entry in DEV_SIGNIN_IDENTITIES:
        if entry["email"] == email:
            return entry
    return None


@dev_signin.route("/dev-signin", methods=["POST"])
def auto():
    """Sign the current session in as one of the well-known dev identities.

    Validates the requested email against ``DEV_SIGNIN_IDENTITIES``, upserts
    a ``client_permissions`` row for that OIDC subject with the entry's role
    (unconditionally overwriting any prior role, so the picker is
    predictable), then establishes the session.

    No credential check. Gated purely by the presence of the blueprint,
    which is itself gated by TF_DEV_AUTO_SIGNIN at app-creation time.
    """
    email = request.form.get("email", "")
    identity = _find_identity(email)
    if identity is None:
        abort(HTTPStatus.BAD_REQUEST, message="Unknown dev sign-in identity")

    # Unconditionally set the role for this identity so the picker is
    # predictable: "whatever you clicked last is your current role".
    database.mongo.db.client_permissions.update_one(
        {"sub": identity["sub"]},
        {
            "$set": {
                "client_id": identity["email"],
                "sub": identity["sub"],
                "role": str(ServerRoles(identity["role"])),
            }
        },
        upsert=True,
    )

    session["user"] = identity["name"]
    session["user_email"] = identity["email"]
    current_app.owasp_logger.warning(
        "Dev auto sign-in used: session established as %s with role %s",
        identity["email"],
        identity["role"],
    )
    return redirect(url_for("testflinger.home"))
