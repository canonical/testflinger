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

Shortcuts are provided for every role -- including contributor -- because
almost every non-public view requires an authenticated session, and there
is currently no "logged in but no role" state that would let us exercise
the contributor code paths without a real session. Going through the full
Dex login flow for every contributor test is friction we don't need in
local dev, so ``carol`` and ``dave`` sit alongside the elevated shortcuts.

Each identity's email must match a ``staticPasswords`` entry in
``devel/dex-config.yaml`` so that the same email works via both the Dex login
path and the dev shortcut (permissions are keyed on ``session["user_email"]``
via ``get_client_permissions``).
"""

import os
from http import HTTPStatus

from apiflask import abort
from flask import Blueprint, current_app, redirect, request, session, url_for

from testflinger import database
from testflinger_common.enums import ServerRoles

# ---------------------------------------------------------------------------
# Well-known development identities, one per role. ``email`` is used both
# as the session ``user_email`` and as the ``client_id`` key when upserting
# ``client_permissions`` (matching how ``register_oidc_client`` maps OIDC
# users to permission rows).
# ---------------------------------------------------------------------------
DEV_SIGNIN_IDENTITIES = [
    {
        "email": "alice@example.com",
        "name": "alice",
        "role": ServerRoles.ADMIN,
        "label": "alice (admin)",
    },
    {
        "email": "bob@example.com",
        "name": "bob",
        "role": ServerRoles.MANAGER,
        "label": "bob (manager)",
    },
    {
        "email": "carol@example.com",
        "name": "carol",
        "role": ServerRoles.CONTRIBUTOR,
        "label": "carol (contributor)",
    },
    {
        "email": "dave@example.com",
        "name": "dave",
        "role": ServerRoles.CONTRIBUTOR,
        "label": "dave (contributor)",
    },
]

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
    a ``client_permissions`` row for that email with the entry's role
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
    database.create_or_update_client_permissions(
        identity["email"],
        {"client_id": identity["email"], "role": str(identity["role"])},
    )

    session["user"] = identity["name"]
    session["user_email"] = identity["email"]
    current_app.owasp_logger.warning(
        "Dev auto sign-in used: session established as %s with role %s",
        identity["email"],
        identity["role"],
    )
    return redirect(url_for("testflinger.home"))
