#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

r"""# Interface Library for traefik_route.

This library wraps relation endpoints for traefik_route. The requirer of this
relation is the traefik-route-k8s charm, or any charm capable of providing
Traefik configuration files. The provider is the traefik-k8s charm, or another
charm willing to consume Traefik configuration files.

## Getting Started

To get started using the library, you just need to fetch the library using `charmcraft`.

```shell
cd some-charm
charmcraft fetch-lib charms.traefik_k8s.v0.traefik_route
```

To use the library from the provider side (Traefik):

```yaml
provides:
    traefik_route:
        interface: traefik_route
        limit: 1
```

```python
from charms.traefik_k8s.v0.traefik_route import TraefikRouteProvider

class TraefikCharm(CharmBase):
  def __init__(self, *args):
    # ...
    self.traefik_route = TraefikRouteProvider(self)

    self.framework.observe(
        self.traefik_route.on.ready, self._handle_traefik_route_ready
    )

    def _handle_traefik_route_ready(self, event):
        config: str = self.traefik_route.get_config(event.relation)  # yaml
        # use config to configure Traefik
```

To use the library from the requirer side (TraefikRoute):

```yaml
requires:
    traefik-route:
        interface: traefik_route
        limit: 1
        optional: false
```

Example usage without raw flag (default behavior):

```python
# ...
from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer

class TraefikRouteCharm(CharmBase):
  def __init__(self, *args):
    # ...
    traefik_route = TraefikRouteRequirer(
        self, self.model.relations.get("traefik-route"),
        "traefik-route",
        raw=False  # Default: Traefik will append TLS configs
    )
    if traefik_route.is_ready():
        traefik_route.submit_to_traefik(
            config={'my': {'traefik': 'configuration'}}
        )
```

Example usage with raw flag enabled (full control over TLS configuration):

```python
# ...
from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer

class TraefikRouteCharm(CharmBase):
  def __init__(self, *args):
    # ...
    traefik_route = TraefikRouteRequirer(
        self, self.model.relations.get("traefik-route"),
        "traefik-route",
        raw=True  # Traefik will not modify TLS settings on all routes
    )
    if self.traefik_route.is_ready():
        self.traefik_route.submit_to_traefik(
            config={
                'tcp': {
                    'routers': {
                        'secure-route': {
                            'rule': 'Host(`secure.example.com`)',
                            'service': 'my-service',
                            'tls': {'certResolver': 'myresolver'}
                        }
                    }
                }
            }
        )
```
"""

import logging
from typing import Optional

import yaml
from ops.charm import CharmBase, CharmEvents, RelationEvent
from ops.framework import EventSource, Object, StoredState
from ops.model import Relation

# The unique Charmhub library identifier, never change it
LIBID = "f0d93d2bdf354b99a527463a9c49fce3"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 5

log = logging.getLogger(__name__)


class TraefikRouteException(RuntimeError):
    """Base class for exceptions raised by TraefikRoute."""


class UnauthorizedError(TraefikRouteException):
    """Raised when the unit needs leadership to perform some action."""


class TraefikRouteProviderReadyEvent(RelationEvent):
    """Event emitted when Traefik is ready to provide ingress for a routed unit."""


class TraefikRouteProviderDataRemovedEvent(RelationEvent):
    """Event emitted when a routed ingress relation is removed."""


class TraefikRouteRequirerReadyEvent(RelationEvent):
    """Event emitted when a unit requesting ingress has provided all data Traefik needs."""


class TraefikRouteRequirerEvents(CharmEvents):
    """Container for TraefikRouteRequirer events."""

    ready = EventSource(TraefikRouteRequirerReadyEvent)


class TraefikRouteProviderEvents(CharmEvents):
    """Container for TraefikRouteProvider events."""

    ready = EventSource(TraefikRouteProviderReadyEvent)  # TODO rename to data_provided in v1
    data_removed = EventSource(TraefikRouteProviderDataRemovedEvent)


class TraefikRouteProvider(Object):
    """Implementation of the provider of traefik_route.

    This will presumably be owned by a Traefik charm.
    The main idea is that Traefik will observe the `ready` event and, upon
    receiving it, will fetch the config from the TraefikRoute's application databag,
    apply it, and update its own app databag to let Route know that the ingress
    is there.
    The TraefikRouteProvider provides api to do this easily.
    """

    on = TraefikRouteProviderEvents()  # pyright: ignore
    _stored = StoredState()

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = "traefik-route",
        external_host: str = "",
        *,
        scheme: str = "http",
    ):
        """Constructor for TraefikRouteProvider.

        Args:
            charm: The charm that is instantiating the instance.
            relation_name: The name of the relation relation_name to bind to
                (defaults to "traefik-route").
            external_host: The external host.
            scheme: The scheme.
        """
        super().__init__(charm, relation_name)
        self._stored.set_default(external_host=None, scheme=None)

        self._charm = charm
        self._relation_name = relation_name

        if (
            self._stored.external_host != external_host  # pyright: ignore
            or self._stored.scheme != scheme  # pyright: ignore
        ):
            # If traefik endpoint details changed, update
            self.update_traefik_address(external_host=external_host, scheme=scheme)

        self.framework.observe(
            self._charm.on[relation_name].relation_changed, self._on_relation_changed
        )
        self.framework.observe(
            self._charm.on[relation_name].relation_broken, self._on_relation_broken
        )

    @property
    def external_host(self) -> str:
        """Return the external host set by Traefik, if any."""
        self._update_stored()
        return self._stored.external_host or ""  # type: ignore

    @property
    def scheme(self) -> str:
        """Return the scheme set by Traefik, if any."""
        self._update_stored()
        return self._stored.scheme or ""  # type: ignore

    @property
    def relations(self) -> list:
        """The list of Relation instances associated with this endpoint."""
        return list(self._charm.model.relations[self._relation_name])

    def _update_stored(self) -> None:
        """Ensure that the stored data is up-to-date.

        This is split out into a separate method since, in the case of multi-unit deployments,
        removal of a `TraefikRouteRequirer` will not cause a `RelationEvent`, but the guard on
        app data ensures that only the previous leader will know what it is. Separating it
        allows for reuse both when the property is called and if the relation changes, so a
        leader change where the new leader checks the property will do the right thing.
        """
        if not self._charm.unit.is_leader():
            return

        for relation in self._charm.model.relations[self._relation_name]:
            if not relation.app:
                self._stored.external_host = ""
                self._stored.scheme = ""
                return
            external_host = relation.data[relation.app].get("external_host", "")
            self._stored.external_host = (
                external_host or self._stored.external_host  # pyright: ignore
            )
            scheme = relation.data[relation.app].get("scheme", "")
            self._stored.scheme = scheme or self._stored.scheme  # pyright: ignore

    def _on_relation_changed(self, event: RelationEvent) -> None:
        if self.is_ready(event.relation):
            # todo check data is valid here?
            self.update_traefik_address()
            self.on.ready.emit(relation=event.relation, app=event.relation.app)

    def _on_relation_broken(self, event: RelationEvent) -> None:
        self.on.data_removed.emit(relation=event.relation, app=event.relation.app)

    def update_traefik_address(
        self, *, external_host: Optional[str] = None, scheme: Optional[str] = None
    ) -> None:
        """Ensure that requirers know the external host for Traefik."""
        if not self._charm.unit.is_leader():
            return

        for relation in self._charm.model.relations[self._relation_name]:
            relation.data[self._charm.app]["external_host"] = external_host or self.external_host
            relation.data[self._charm.app]["scheme"] = scheme or self.scheme

        # We first attempt to write relation data (which may raise) and only then update stored
        # state.
        self._stored.external_host = external_host
        self._stored.scheme = scheme

    def is_ready(self, relation: Relation) -> bool:
        """Whether TraefikRoute is ready on this relation.

        Returns True when the remote app shared the config; False otherwise.
        """
        if not relation.app or not relation.data[relation.app]:
            return False
        return "config" in relation.data[relation.app]

    def get_config(self, relation: Relation) -> Optional[str]:
        """Renamed to ``get_dynamic_config``."""
        log.warning(
            "``TraefikRouteProvider.get_config`` is deprecated. "
            "Use ``TraefikRouteProvider.get_dynamic_config`` instead"
        )
        return self.get_dynamic_config(relation)

    def get_dynamic_config(self, relation: Relation) -> Optional[str]:
        """Retrieve the dynamic config published by the remote application."""
        if not self.is_ready(relation):
            return None
        return relation.data[relation.app].get("config")

    def is_raw_enabled(self, relation: Relation) -> bool:
        """Check if the raw config mode is enabled by the remote application."""
        if not self.is_ready(relation):
            return False
        return relation.data[relation.app].get("raw") == "True"

    def get_static_config(self, relation: Relation) -> Optional[str]:
        """Retrieve the static config published by the remote application."""
        if not self.is_ready(relation):
            return None
        return relation.data[relation.app].get("static")


class TraefikRouteRequirer(Object):
    """Handles the requirer side of the traefik-route interface.

    This class provides an API for publishing dynamic and static configurations
    to the Traefik charm through the `traefik-route` relation. It does not perform
    validation on the provided configurations, assuming that Traefik will handle
    valid YAML-encoded data.

    The application databag follows the structure:

    ```json
    {
        "config": "<Traefik dynamic config YAML>",
        "static": "<Traefik static config YAML>",  # Optional, requires Traefik restart
        "raw": "<bool>"  # Determines if Traefik should append TLS config for ALL routes
    }
    ```

    """

    on = TraefikRouteRequirerEvents()  # pyright: ignore
    _stored = StoredState()

    def __init__(
        self,
        charm: CharmBase,
        relation: Relation,
        relation_name: str = "traefik-route",
        raw: Optional[bool] = False,
    ):
        """Initialize the traefik-route requirer class.

        Args:
            charm: Requirer charm.
            relation: traefik-route relation.
            relation_name: Name of the relation. Defaults to "traefik-route".
            raw: Whether or not to enable raw mode. Defaults to False.
        """
        super(TraefikRouteRequirer, self).__init__(charm, relation_name)
        self._stored.set_default(external_host=None, scheme=None)

        self._charm = charm
        self._relation = relation
        self._raw = raw

        if self._raw:
            log.warning(
                "Raw mode enabled: TLS routes for ALL protocols will not be auto-generated. "
                "Enable this only if you fully understand and intend to bypass the additional"
                "TLS configuration."
            )

        self.framework.observe(
            self._charm.on[relation_name].relation_changed, self._on_relation_changed
        )
        self.framework.observe(
            self._charm.on[relation_name].relation_broken, self._on_relation_broken
        )

    @property
    def external_host(self) -> str:
        """Return the external host set by Traefik, if any."""
        self._update_stored()
        return self._stored.external_host or ""  # type: ignore

    @property
    def scheme(self) -> str:
        """Return the scheme set by Traefik, if any."""
        self._update_stored()
        return self._stored.scheme or ""  # type: ignore

    def _update_stored(self) -> None:
        """Ensure that the stored host is up-to-date.

        This is split out into a separate method since, in the case of multi-unit deployments,
        removal of a `TraefikRouteRequirer` will not cause a `RelationEvent`, but the guard on
        app data ensures that only the previous leader will know what it is. Separating it
        allows for reuse both when the property is called and if the relation changes, so a
        leader change where the new leader checks the property will do the right thing.
        """
        if not self._charm.unit.is_leader():
            return

        if self._relation:
            for relation in self._charm.model.relations[self._relation.name]:
                if not relation.app:
                    self._stored.external_host = ""
                    self._stored.scheme = ""
                    return
                external_host = relation.data[relation.app].get("external_host", "")
                self._stored.external_host = (
                    external_host or self._stored.external_host  # pyright: ignore
                )
                scheme = relation.data[relation.app].get("scheme", "")
                self._stored.scheme = scheme or self._stored.scheme  # pyright: ignore

    def _on_relation_changed(self, event: RelationEvent) -> None:
        """Update StoredState with external_host and other information from Traefik."""
        self._update_stored()
        if self._charm.unit.is_leader():
            self.on.ready.emit(relation=event.relation, app=event.relation.app)

    def _on_relation_broken(self, event: RelationEvent) -> None:
        """On RelationBroken, clear the stored data if set and emit an event."""
        self._stored.external_host = ""
        if self._charm.unit.is_leader():
            self.on.ready.emit(relation=event.relation, app=event.relation.app)

    def is_ready(self) -> bool:
        """Is the TraefikRouteRequirer ready to submit data to Traefik?"""
        return self._relation is not None

    def submit_to_traefik(self, config: dict, static: Optional[dict] = None) -> None:
        """Submit an ingress configuration to Traefik.

        This method publishes dynamic and static configuration data to the
        `traefik-route` relation, allowing Traefik to pick up and apply the settings.

        - **Dynamic config (`config`)**: Defines routing rules for Traefik.
        - **Static config (`static`)**: Requires a Traefik restart to take effect.

        Raises:
            UnauthorizedError: If the unit is not the leader.
        """
        if not self._charm.unit.is_leader():
            raise UnauthorizedError()

        app_databag = self._relation.data[self._charm.app]

        app_databag["raw"] = str(self._raw)

        # Traefik thrives on YAML, feels pointless to talk JSON to Route
        app_databag["config"] = yaml.safe_dump(config)

        if static:
            app_databag["static"] = yaml.safe_dump(static)
