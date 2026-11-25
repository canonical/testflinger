#!/usr/bin/env python3
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
"""Generate local Dex data from sample users."""

from pathlib import Path

from sample_users import SAMPLE_CLIENTS

ROOT = Path(__file__).parent.parent
PASSWORD_HASH = "$2a$10$FWI.y.8Zpa9PhTTcV6GDIuxPzrwYJoiVCimgCA427HoyR5FR50mBu"


def _write_dex_config() -> None:
    """Write Dex configuration for all sample clients with an OIDC identity."""
    dex_users = [
        client
        for client in SAMPLE_CLIENTS.values()
        if client.get("dex_account")
    ]
    lines = [
        "issuer: http://dex:5556",
        "storage:",
        "  type: memory",
        "web:",
        "  http: 0.0.0.0:5556",
        "staticClients:",
        "  - id: testflinger-client",
        "    redirectURIs:",
        "      - 'http://testflinger-server:5000/auth/callback'",
        "      - 'http://localhost:5000/auth/callback'",
        "      - 'http://127.0.0.1:5000/auth/callback'",
        "      - '/device/callback'",
        "    name: 'Testflinger Dev'",
        "    public: true",
        "    grantTypes:",
        "enablePasswordDB: true",
        "staticPasswords:",
    ]
    for user in dex_users:
        lines.extend(
            [
                f'  - email: "{user["email"]}"',
                f'    hash: "{PASSWORD_HASH}"',
                f'    username: "{user["name"]}"',
                f'    userID: "{user["dex_user_id"]}"',
            ]
        )
    lines.extend(
        [
            "oauth2:",
            "  grantTypes:",
            '    - "authorization_code"',
            '    - "refresh_token"',
            '    - "urn:ietf:params:oauth:grant-type:device_code"',
            "",
        ]
    )
    (ROOT / "devel/dex-config.yaml").write_text("\n".join(lines))


def main() -> None:
    """Generate all local account consumer inputs."""
    _write_dex_config()


if __name__ == "__main__":
    main()
