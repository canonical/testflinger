# Copyright 2026 Canonical
# See LICENSE file for licensing details.
import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path

import requests
from common import write_file
from defaults import DEFAULT_TOKEN_PATH

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15
REFRESH_TOKEN_LIFETIME_DAYS = 30


def post_request(
    uri: str, headers: dict, timeout: int = DEFAULT_TIMEOUT
) -> dict:
    """Send a POST request to the specified URI with given headers.

    :param uri: The target URI for the POST request.
    :param headers: A dictionary of headers to include in the request.
    :return: The response object from the POST request.
    """
    try:
        response = requests.post(uri, headers=headers, timeout=timeout)
    except requests.exceptions.ConnectTimeout:
        logger.error("Connection to Testflinger server timed out.")
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to Testflinger server.")

    if response and response.status_code == HTTPStatus.OK:
        return response.json()

    logger.error(
        "Authentication failed with status code: %s", response.status_code
    )
    return None


def authenticate(server: str, client_id: str, secret_key: str) -> bool:
    """Authenticate the Testflinger client using provided credentials.

    This also stores the refresh token for persistent agents login.

    :param client_id: Agent Host client id.
    :param secret_key: Agent Host client secret.

    :returns: True if authentication succeeded, False otherwise.
    """
    uri = f"{server}/v1/oauth2/token"
    id_key_pair = f"{client_id}:{secret_key}"
    encoded_id_key_pair = base64.b64encode(id_key_pair.encode("utf-8")).decode(
        "utf-8"
    )
    headers = {"Authorization": f"Basic {encoded_id_key_pair}"}
    token_request = post_request(uri, headers)

    if token_request:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS)
        token_data = {
            "refresh_token": token_request.get("refresh_token"),
            "obtained_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        token_path = Path(DEFAULT_TOKEN_PATH)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        write_file(token_path, json.dumps(token_data))
        return True
    return False


def get_token_data() -> dict | None:
    """Read and parse the stored token data.

    :returns: Token data dict or None if file doesn't exist or is invalid.
    """
    token_path = Path(DEFAULT_TOKEN_PATH)
    if not token_path.exists():
        return None
    try:
        return json.loads(token_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read token file: %s", exc)
        return None


def token_update_needed(days_threshold: int = 7) -> bool:
    """Check if the refresh token is expiring within the threshold.

    By default, refresh tokens expire after 30 days on server side.

    :param days_threshold: Number of days before expiration to trigger refresh.
    :returns: True if token is missing, invalid, or expiring soon.
    """
    token_data = get_token_data()
    if not token_data:
        return True

    try:
        expires_at = datetime.fromisoformat(token_data["expires_at"])
        threshold = datetime.now(timezone.utc) + timedelta(days=days_threshold)
        return expires_at <= threshold
    except (KeyError, ValueError) as exc:
        logger.error("Invalid token data: %s", exc)
        return True
