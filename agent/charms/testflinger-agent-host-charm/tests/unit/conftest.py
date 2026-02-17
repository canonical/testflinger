# Copyright 2026 Canonical
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

from collections.abc import Callable

import pytest
from charm import TestflingerAgentHostCharm
from ops import testing


@pytest.fixture
def ctx() -> testing.Context:
    """Fixture to create a testing context for the charm."""
    return testing.Context(TestflingerAgentHostCharm)


@pytest.fixture
def secret() -> testing.Secret:
    """Fixture to create a testing secret with valid credentials."""
    return testing.Secret(
        tracked_content={"client-id": "test-id", "secret-key": "test-key"},
    )


@pytest.fixture
def state_in() -> Callable[..., testing.State]:
    """Create a testing state with configurable config and secrets."""

    def _state_in(
        *, config: dict | None = None, secrets: list | None = None
    ) -> testing.State:
        default_config = {
            "config-repo": "some-repo",
            "config-dir": "agent-configs",
        }
        if config:
            default_config.update(config)
        return testing.State(config=default_config, secrets=secrets or [])

    return _state_in
