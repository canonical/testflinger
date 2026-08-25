# Copyright (C) 2025 Canonical
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

"""Support for forwarding job status updates to different webhook types.

Testflinger jobs may point their ``job_status_webhook`` at services that
expect very different requests. This module turns a webhook definition
(either a plain URL or an object with an explicit ``type``) into the
concrete HTTP request that has to be issued for that service.

Support for a new webhook type is added by extending :class:`WebhookType`
with the new type, teaching :func:`detect_webhook_type` how to recognise it
and registering a request builder for it in ``_REQUEST_BUILDERS``.
"""

from dataclasses import dataclass, field
from enum import Enum

#: Seconds to wait for a webhook endpoint to respond.
WEBHOOK_TIMEOUT = 3

#: URL prefixes recognised as Mattermost incoming webhooks. Mattermost
#: incoming webhooks all live under ``/hooks/`` on their server, so matching
#: the full prefix avoids misclassifying unrelated endpoints that happen to
#: use the same path.
MATTERMOST_URL_PREFIXES = ("https://chat.canonical.com/hooks/",)


class WebhookError(Exception):
    """Raised when a webhook definition cannot be turned into a request."""


class WebhookType(str, Enum):
    """The webhook flavours that the server knows how to talk to."""

    DEFAULT_WEBHOOK = "default"
    MATTERMOST = "mattermost"


def detect_webhook_type(url: str) -> WebhookType:
    """Infer the webhook type from the shape of its URL.

    This keeps job definitions that only specify a plain URL working, while
    still routing them to the correct handler. A job can always override the
    inferred type by specifying the webhook as an object instead.

    :param url: the webhook URL
    :return: the inferred :class:`WebhookType`
    """
    if url.startswith(MATTERMOST_URL_PREFIXES):
        return WebhookType.MATTERMOST
    return WebhookType.DEFAULT_WEBHOOK


@dataclass(frozen=True)
class WebhookSpec:
    """A normalised webhook definition taken from a job."""

    url: str
    type: WebhookType

    @classmethod
    def from_definition(cls, definition: str | dict) -> "WebhookSpec":
        """Normalise a job webhook definition.

        :param definition:
            either a URL string or a mapping with at least a ``url`` key
        :raises KeyError: if a mapping does not specify a ``url``
        :raises ValueError: if an unknown webhook type is specified
        :return: the corresponding :class:`WebhookSpec`
        """
        if isinstance(definition, str):
            definition = {"url": definition}

        url = definition["url"]
        webhook_type = definition.get("type")
        return cls(
            url=url,
            type=(
                WebhookType(webhook_type)
                if webhook_type
                else detect_webhook_type(url)
            ),
        )


@dataclass
class WebhookRequest:
    """The HTTP request to issue for a single webhook."""

    method: str
    url: str
    json: dict
    headers: dict = field(default_factory=dict)


def _latest_event(status_update: dict) -> dict:
    """Return the most recent event of a status update, if any."""
    events = status_update.get("events") or []
    return events[-1] if events else {}


def _default_webhook_request(
    spec: WebhookSpec,
    status_update: dict,
    job_id: str,
    job_url: str,
    auth_headers: dict,
) -> WebhookRequest:
    """Build the request for a default style webhook.

    The status update is forwarded verbatim, using the credential configured
    server-side. This is the behaviour that webhook consumers relied on
    before other webhook types were supported, so it stays the default.
    """
    del job_id, job_url
    return WebhookRequest(
        method="PUT",
        url=spec.url,
        json=status_update,
        headers=auth_headers,
    )


def _mattermost_request(
    spec: WebhookSpec,
    status_update: dict,
    job_id: str,
    job_url: str,
    auth_headers: dict,
) -> WebhookRequest:
    """Build the request for a Mattermost incoming webhook.

    Mattermost incoming webhooks only accept ``POST`` with a ``text`` field
    and are authenticated by the secret embedded in their URL, so the
    server credential is deliberately not attached to them.
    """
    del auth_headers

    job_reference = f"[`{job_id}`]({job_url})" if job_url else f"`{job_id}`"
    lines = [f"**Testflinger job** {job_reference}"]

    if job_queue := status_update.get("job_queue"):
        lines.append(f"- Queue: `{job_queue}`")
    if agent_id := status_update.get("agent_id"):
        lines.append(f"- Agent: `{agent_id}`")

    event = _latest_event(status_update)
    if event_name := event.get("event_name"):
        timestamp = event.get("timestamp", "")
        lines.append(f"- Event: `{event_name}` {timestamp}".rstrip())
    if detail := event.get("detail"):
        lines.append(f"- Detail: {detail}")

    return WebhookRequest(
        method="POST",
        url=spec.url,
        json={"text": "\n".join(lines)},
    )


#: Request builder for each supported webhook type.
_REQUEST_BUILDERS = {
    WebhookType.DEFAULT_WEBHOOK: _default_webhook_request,
    WebhookType.MATTERMOST: _mattermost_request,
}


def build_request(
    spec: WebhookSpec,
    status_update: dict,
    job_id: str,
    job_url: str = "",
    auth_headers: dict | None = None,
) -> WebhookRequest:
    """Build the HTTP request for a single webhook.

    :param spec: the normalised webhook definition
    :param status_update: the status update posted by the agent
    :param job_id: UUID as a string for the job
    :param job_url: URL of the job in the Testflinger web UI
    :param auth_headers:
        headers holding the server-wide default webhook credential; it is up
        to each request builder to decide whether they are appropriate for
        the webhook it targets
    :raises WebhookError: if the webhook cannot be delivered as defined
    :return: the request to issue
    """
    try:
        build = _REQUEST_BUILDERS[spec.type]
    except KeyError:
        raise WebhookError(
            f"Unsupported webhook type '{spec.type}' for {spec.url}"
        ) from None

    return build(
        spec, status_update, job_id, job_url, dict(auth_headers or {})
    )
