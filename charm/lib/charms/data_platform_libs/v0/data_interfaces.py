# Copyright 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Library to manage the relation for the data-platform products.

This library contains the Requires and Provides classes for handling the relation
between an application and multiple managed application supported by the data-team:
MySQL, Postgresql, MongoDB, Redis, and Kafka.

### Database (MySQL, Postgresql, MongoDB, and Redis)

#### Requires Charm
This library is a uniform interface to a selection of common database
metadata, with added custom events that add convenience to database management,
and methods to consume the application related data.


Following an example of using the DatabaseCreatedEvent, in the context of the
application charm code:

```python

from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseRequires,
)

class ApplicationCharm(CharmBase):
    # Application charm that connects to database charms.

    def __init__(self, *args):
        super().__init__(*args)

        # Charm events defined in the database requires charm library.
        self.database = DatabaseRequires(self, relation_name="database", database_name="database")
        self.framework.observe(self.database.on.database_created, self._on_database_created)

    def _on_database_created(self, event: DatabaseCreatedEvent) -> None:
        # Handle the created database

        # Create configuration file for app
        config_file = self._render_app_config_file(
            event.username,
            event.password,
            event.endpoints,
        )

        # Start application with rendered configuration
        self._start_application(config_file)

        # Set active status
        self.unit.status = ActiveStatus("received database credentials")
```

As shown above, the library provides some custom events to handle specific situations,
which are listed below:

-  database_created: event emitted when the requested database is created.
-  endpoints_changed: event emitted when the read/write endpoints of the database have changed.
-  read_only_endpoints_changed: event emitted when the read-only endpoints of the database
  have changed. Event is not triggered if read/write endpoints changed too.

If it is needed to connect multiple database clusters to the same relation endpoint
the application charm can implement the same code as if it would connect to only
one database cluster (like the above code example).

To differentiate multiple clusters connected to the same relation endpoint
the application charm can use the name of the remote application:

```python

def _on_database_created(self, event: DatabaseCreatedEvent) -> None:
    # Get the remote app name of the cluster that triggered this event
    cluster = event.relation.app.name
```

It is also possible to provide an alias for each different database cluster/relation.

So, it is possible to differentiate the clusters in two ways.
The first is to use the remote application name, i.e., `event.relation.app.name`, as above.

The second way is to use different event handlers to handle each cluster events.
The implementation would be something like the following code:

```python

from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseRequires,
)

class ApplicationCharm(CharmBase):
    # Application charm that connects to database charms.

    def __init__(self, *args):
        super().__init__(*args)

        # Define the cluster aliases and one handler for each cluster database created event.
        self.database = DatabaseRequires(
            self,
            relation_name="database",
            database_name="database",
            relations_aliases = ["cluster1", "cluster2"],
        )
        self.framework.observe(
            self.database.on.cluster1_database_created, self._on_cluster1_database_created
        )
        self.framework.observe(
            self.database.on.cluster2_database_created, self._on_cluster2_database_created
        )

    def _on_cluster1_database_created(self, event: DatabaseCreatedEvent) -> None:
        # Handle the created database on the cluster named cluster1

        # Create configuration file for app
        config_file = self._render_app_config_file(
            event.username,
            event.password,
            event.endpoints,
        )
        ...

    def _on_cluster2_database_created(self, event: DatabaseCreatedEvent) -> None:
        # Handle the created database on the cluster named cluster2

        # Create configuration file for app
        config_file = self._render_app_config_file(
            event.username,
            event.password,
            event.endpoints,
        )
        ...

```

When it's needed to check whether a plugin (extension) is enabled on the PostgreSQL
charm, you can use the is_postgresql_plugin_enabled method. To use that, you need to
add the following dependency to your charmcraft.yaml file:

```yaml

parts:
  charm:
    charm-binary-python-packages:
      - psycopg[binary]

```

### Provider Charm

Following an example of using the DatabaseRequestedEvent, in the context of the
database charm code:

```python
from charms.data_platform_libs.v0.data_interfaces import DatabaseProvides

class SampleCharm(CharmBase):

    def __init__(self, *args):
        super().__init__(*args)
        # Charm events defined in the database provides charm library.
        self.provided_database = DatabaseProvides(self, relation_name="database")
        self.framework.observe(self.provided_database.on.database_requested,
            self._on_database_requested)
        # Database generic helper
        self.database = DatabaseHelper()

    def _on_database_requested(self, event: DatabaseRequestedEvent) -> None:
        # Handle the event triggered by a new database requested in the relation
        # Retrieve the database name using the charm library.
        db_name = event.database
        # generate a new user credential
        username = self.database.generate_user()
        password = self.database.generate_password()
        # set the credentials for the relation
        self.provided_database.set_credentials(event.relation.id, username, password)
        # set other variables for the relation event.set_tls("False")
```
As shown above, the library provides a custom event (database_requested) to handle
the situation when an application charm requests a new database to be created.
It's preferred to subscribe to this event instead of relation changed event to avoid
creating a new database when other information other than a database name is
exchanged in the relation databag.

### Kafka

This library is the interface to use and interact with the Kafka charm. This library contains
custom events that add convenience to manage Kafka, and provides methods to consume the
application related data.

#### Requirer Charm

```python

from charms.data_platform_libs.v0.data_interfaces import (
    BootstrapServerChangedEvent,
    KafkaRequires,
    TopicCreatedEvent,
)

class ApplicationCharm(CharmBase):

    def __init__(self, *args):
        super().__init__(*args)
        self.kafka = KafkaRequires(self, "kafka_client", "test-topic")
        self.framework.observe(
            self.kafka.on.bootstrap_server_changed, self._on_kafka_bootstrap_server_changed
        )
        self.framework.observe(
            self.kafka.on.topic_created, self._on_kafka_topic_created
        )

    def _on_kafka_bootstrap_server_changed(self, event: BootstrapServerChangedEvent):
        # Event triggered when a bootstrap server was changed for this application

        new_bootstrap_server = event.bootstrap_server
        ...

    def _on_kafka_topic_created(self, event: TopicCreatedEvent):
        # Event triggered when a topic was created for this application
        username = event.username
        password = event.password
        tls = event.tls
        tls_ca= event.tls_ca
        bootstrap_server event.bootstrap_server
        consumer_group_prefic = event.consumer_group_prefix
        zookeeper_uris = event.zookeeper_uris
        ...

```

As shown above, the library provides some custom events to handle specific situations,
which are listed below:

- topic_created: event emitted when the requested topic is created.
- bootstrap_server_changed: event emitted when the bootstrap server have changed.
- credential_changed: event emitted when the credentials of Kafka changed.

### Provider Charm

Following the previous example, this is an example of the provider charm.

```python
class SampleCharm(CharmBase):

from charms.data_platform_libs.v0.data_interfaces import (
    KafkaProvides,
    TopicRequestedEvent,
)

    def __init__(self, *args):
        super().__init__(*args)

        # Default charm events.
        self.framework.observe(self.on.start, self._on_start)

        # Charm events defined in the Kafka Provides charm library.
        self.kafka_provider = KafkaProvides(self, relation_name="kafka_client")
        self.framework.observe(self.kafka_provider.on.topic_requested, self._on_topic_requested)
        # Kafka generic helper
        self.kafka = KafkaHelper()

    def _on_topic_requested(self, event: TopicRequestedEvent):
        # Handle the on_topic_requested event.

        topic = event.topic
        relation_id = event.relation.id
        # set connection info in the databag relation
        self.kafka_provider.set_bootstrap_server(relation_id, self.kafka.get_bootstrap_server())
        self.kafka_provider.set_credentials(relation_id, username=username, password=password)
        self.kafka_provider.set_consumer_group_prefix(relation_id, ...)
        self.kafka_provider.set_tls(relation_id, "False")
        self.kafka_provider.set_zookeeper_uris(relation_id, ...)

```
As shown above, the library provides a custom event (topic_requested) to handle
the situation when an application charm requests a new topic to be created.
It is preferred to subscribe to this event instead of relation changed event to avoid
creating a new topic when other information other than a topic name is
exchanged in the relation databag.
"""

import json
import logging
from abc import ABC, abstractmethod
from collections import namedtuple
from datetime import datetime
from typing import List, Optional

from ops.charm import (
    CharmBase,
    CharmEvents,
    RelationChangedEvent,
    RelationEvent,
    RelationJoinedEvent,
)
from ops.framework import EventSource, Object
from ops.model import Relation

# The unique Charmhub library identifier, never change it
LIBID = "6c3e6b6680d64e9c89e611d1a15f65be"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 12

PYDEPS = ["ops>=2.0.0"]

logger = logging.getLogger(__name__)

Diff = namedtuple("Diff", "added changed deleted")
Diff.__doc__ = """
A tuple for storing the diff between two data mappings.

added - keys that were added
changed - keys that still exist but have new values
deleted - key that were deleted"""


def diff(event: RelationChangedEvent, bucket: str) -> Diff:
    """Retrieves the diff of the data in the relation changed databag.

    Args:
        event: relation changed event.
        bucket: bucket of the databag (app or unit)

    Returns:
        a Diff instance containing the added, deleted and changed
            keys from the event relation databag.
    """
    # Retrieve the old data from the data key in the application relation databag.
    old_data = json.loads(event.relation.data[bucket].get("data", "{}"))
    # Retrieve the new data from the event relation databag.
    new_data = {
        key: value for key, value in event.relation.data[event.app].items() if key != "data"
    }

    # These are the keys that were added to the databag and triggered this event.
    added = new_data.keys() - old_data.keys()
    # These are the keys that were removed from the databag and triggered this event.
    deleted = old_data.keys() - new_data.keys()
    # These are the keys that already existed in the databag,
    # but had their values changed.
    changed = {key for key in old_data.keys() & new_data.keys() if old_data[key] != new_data[key]}
    # Convert the new_data to a serializable format and save it for a next diff check.
    event.relation.data[bucket].update({"data": json.dumps(new_data)})

    # Return the diff with all possible changes.
    return Diff(added, changed, deleted)


# Base DataProvides and DataRequires


class DataProvides(Object, ABC):
    """Base provides-side of the data products relation."""

    def __init__(self, charm: CharmBase, relation_name: str) -> None:
        super().__init__(charm, relation_name)
        self.charm = charm
        self.local_app = self.charm.model.app
        self.local_unit = self.charm.unit
        self.relation_name = relation_name
        self.framework.observe(
            charm.on[relation_name].relation_changed,
            self._on_relation_changed,
        )

    def _diff(self, event: RelationChangedEvent) -> Diff:
        """Retrieves the diff of the data in the relation changed databag.

        Args:
            event: relation changed event.

        Returns:
            a Diff instance containing the added, deleted and changed
                keys from the event relation databag.
        """
        return diff(event, self.local_app)

    @abstractmethod
    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Event emitted when the relation data has changed."""
        raise NotImplementedError

    def fetch_relation_data(self) -> dict:
        """Retrieves data from relation.

        This function can be used to retrieve data from a relation
        in the charm code when outside an event callback.

        Returns:
            a dict of the values stored in the relation data bag
                for all relation instances (indexed by the relation id).
        """
        data = {}
        for relation in self.relations:
            data[relation.id] = {
                key: value for key, value in relation.data[relation.app].items() if key != "data"
            }
        return data

    def _update_relation_data(self, relation_id: int, data: dict) -> None:
        """Updates a set of key-value pairs in the relation.

        This function writes in the application data bag, therefore,
        only the leader unit can call it.

        Args:
            relation_id: the identifier for a particular relation.
            data: dict containing the key-value pairs
                that should be updated in the relation.
        """
        if self.local_unit.is_leader():
            relation = self.charm.model.get_relation(self.relation_name, relation_id)
            relation.data[self.local_app].update(data)

    @property
    def relations(self) -> List[Relation]:
        """The list of Relation instances associated with this relation_name."""
        return list(self.charm.model.relations[self.relation_name])

    def set_credentials(self, relation_id: int, username: str, password: str) -> None:
        """Set credentials.

        This function writes in the application data bag, therefore,
        only the leader unit can call it.

        Args:
            relation_id: the identifier for a particular relation.
            username: user that was created.
            password: password of the created user.
        """
        self._update_relation_data(
            relation_id,
            {
                "username": username,
                "password": password,
            },
        )

    def set_tls(self, relation_id: int, tls: str) -> None:
        """Set whether TLS is enabled.

        Args:
            relation_id: the identifier for a particular relation.
            tls: whether tls is enabled (True or False).
        """
        self._update_relation_data(relation_id, {"tls": tls})

    def set_tls_ca(self, relation_id: int, tls_ca: str) -> None:
        """Set the TLS CA in the application relation databag.

        Args:
            relation_id: the identifier for a particular relation.
            tls_ca: TLS certification authority.
        """
        self._update_relation_data(relation_id, {"tls-ca": tls_ca})


class DataRequires(Object, ABC):
    """Requires-side of the relation."""

    def __init__(
        self,
        charm,
        relation_name: str,
        extra_user_roles: str = None,
    ):
        """Manager of base client relations."""
        super().__init__(charm, relation_name)
        self.charm = charm
        self.extra_user_roles = extra_user_roles
        self.local_app = self.charm.model.app
        self.local_unit = self.charm.unit
        self.relation_name = relation_name
        self.framework.observe(
            self.charm.on[relation_name].relation_joined, self._on_relation_joined_event
        )
        self.framework.observe(
            self.charm.on[relation_name].relation_changed, self._on_relation_changed_event
        )

    @abstractmethod
    def _on_relation_joined_event(self, event: RelationJoinedEvent) -> None:
        """Event emitted when the application joins the relation."""
        raise NotImplementedError

    @abstractmethod
    def _on_relation_changed_event(self, event: RelationChangedEvent) -> None:
        raise NotImplementedError

    def fetch_relation_data(self) -> dict:
        """Retrieves data from relation.

        This function can be used to retrieve data from a relation
        in the charm code when outside an event callback.
        Function cannot be used in `*-relation-broken` events and will raise an exception.

        Returns:
            a dict of the values stored in the relation data bag
                for all relation instances (indexed by the relation ID).
        """
        data = {}
        for relation in self.relations:
            data[relation.id] = {
                key: value for key, value in relation.data[relation.app].items() if key != "data"
            }
        return data

    def _update_relation_data(self, relation_id: int, data: dict) -> None:
        """Updates a set of key-value pairs in the relation.

        This function writes in the application data bag, therefore,
        only the leader unit can call it.

        Args:
            relation_id: the identifier for a particular relation.
            data: dict containing the key-value pairs
                that should be updated in the relation.
        """
        if self.local_unit.is_leader():
            relation = self.charm.model.get_relation(self.relation_name, relation_id)
            relation.data[self.local_app].update(data)

    def _diff(self, event: RelationChangedEvent) -> Diff:
        """Retrieves the diff of the data in the relation changed databag.

        Args:
            event: relation changed event.

        Returns:
            a Diff instance containing the added, deleted and changed
                keys from the event relation databag.
        """
        return diff(event, self.local_unit)

    @property
    def relations(self) -> List[Relation]:
        """The list of Relation instances associated with this relation_name."""
        return [
            relation
            for relation in self.charm.model.relations[self.relation_name]
            if self._is_relation_active(relation)
        ]

    @staticmethod
    def _is_relation_active(relation: Relation):
        try:
            _ = repr(relation.data)
            return True
        except RuntimeError:
            return False

    @staticmethod
    def _is_resource_created_for_relation(relation: Relation):
        return (
            "username" in relation.data[relation.app] and "password" in relation.data[relation.app]
        )

    def is_resource_created(self, relation_id: Optional[int] = None) -> bool:
        """Check if the resource has been created.

        This function can be used to check if the Provider answered with data in the charm code
        when outside an event callback.

        Args:
            relation_id (int, optional): When provided the check is done only for the relation id
                provided, otherwise the check is done for all relations

        Returns:
            True or False

        Raises:
            IndexError: If relation_id is provided but that relation does not exist
        """
        if relation_id is not None:
            try:
                relation = [relation for relation in self.relations if relation.id == relation_id][
                    0
                ]
                return self._is_resource_created_for_relation(relation)
            except IndexError:
                raise IndexError(f"relation id {relation_id} cannot be accessed")
        else:
            return (
                all(
                    [
                        self._is_resource_created_for_relation(relation)
                        for relation in self.relations
                    ]
                )
                if self.relations
                else False
            )


# General events


class ExtraRoleEvent(RelationEvent):
    """Base class for data events."""

    @property
    def extra_user_roles(self) -> Optional[str]:
        """Returns the extra user roles that were requested."""
        return self.relation.data[self.relation.app].get("extra-user-roles")


class AuthenticationEvent(RelationEvent):
    """Base class for authentication fields for events."""

    @property
    def username(self) -> Optional[str]:
        """Returns the created username."""
        return self.relation.data[self.relation.app].get("username")

    @property
    def password(self) -> Optional[str]:
        """Returns the password for the created user."""
        return self.relation.data[self.relation.app].get("password")

    @property
    def tls(self) -> Optional[str]:
        """Returns whether TLS is configured."""
        return self.relation.data[self.relation.app].get("tls")

    @property
    def tls_ca(self) -> Optional[str]:
        """Returns TLS CA."""
        return self.relation.data[self.relation.app].get("tls-ca")


# Database related events and fields


class DatabaseProvidesEvent(RelationEvent):
    """Base class for database events."""

    @property
    def database(self) -> Optional[str]:
        """Returns the database that was requested."""
        return self.relation.data[self.relation.app].get("database")


class DatabaseRequestedEvent(DatabaseProvidesEvent, ExtraRoleEvent):
    """Event emitted when a new database is requested for use on this relation."""


class DatabaseProvidesEvents(CharmEvents):
    """Database events.

    This class defines the events that the database can emit.
    """

    database_requested = EventSource(DatabaseRequestedEvent)


class DatabaseRequiresEvent(RelationEvent):
    """Base class for database events."""

    @property
    def database(self) -> Optional[str]:
        """Returns the database name."""
        return self.relation.data[self.relation.app].get("database")

    @property
    def endpoints(self) -> Optional[str]:
        """Returns a comma separated list of read/write endpoints.

        In VM charms, this is the primary's address.
        In kubernetes charms, this is the service to the primary pod.
        """
        return self.relation.data[self.relation.app].get("endpoints")

    @property
    def read_only_endpoints(self) -> Optional[str]:
        """Returns a comma separated list of read only endpoints.

        In VM charms, this is the address of all the secondary instances.
        In kubernetes charms, this is the service to all replica pod instances.
        """
        return self.relation.data[self.relation.app].get("read-only-endpoints")

    @property
    def replset(self) -> Optional[str]:
        """Returns the replicaset name.

        MongoDB only.
        """
        return self.relation.data[self.relation.app].get("replset")

    @property
    def uris(self) -> Optional[str]:
        """Returns the connection URIs.

        MongoDB, Redis, OpenSearch.
        """
        return self.relation.data[self.relation.app].get("uris")

    @property
    def version(self) -> Optional[str]:
        """Returns the version of the database.

        Version as informed by the database daemon.
        """
        return self.relation.data[self.relation.app].get("version")


class DatabaseCreatedEvent(AuthenticationEvent, DatabaseRequiresEvent):
    """Event emitted when a new database is created for use on this relation."""


class DatabaseEndpointsChangedEvent(AuthenticationEvent, DatabaseRequiresEvent):
    """Event emitted when the read/write endpoints are changed."""


class DatabaseReadOnlyEndpointsChangedEvent(AuthenticationEvent, DatabaseRequiresEvent):
    """Event emitted when the read only endpoints are changed."""


class DatabaseRequiresEvents(CharmEvents):
    """Database events.

    This class defines the events that the database can emit.
    """

    database_created = EventSource(DatabaseCreatedEvent)
    endpoints_changed = EventSource(DatabaseEndpointsChangedEvent)
    read_only_endpoints_changed = EventSource(DatabaseReadOnlyEndpointsChangedEvent)


# Database Provider and Requires


class DatabaseProvides(DataProvides):
    """Provider-side of the database relations."""

    on = DatabaseProvidesEvents()

    def __init__(self, charm: CharmBase, relation_name: str) -> None:
        super().__init__(charm, relation_name)

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Event emitted when the relation has changed."""
        # Only the leader should handle this event.
        if not self.local_unit.is_leader():
            return

        # Check which data has changed to emit customs events.
        diff = self._diff(event)

        # Emit a database requested event if the setup key (database name and optional
        # extra user roles) was added to the relation databag by the application.
        if "database" in diff.added:
            self.on.database_requested.emit(event.relation, app=event.app, unit=event.unit)

    def set_database(self, relation_id: int, database_name: str) -> None:
        """Set database name.

        This function writes in the application data bag, therefore,
        only the leader unit can call it.

        Args:
            relation_id: the identifier for a particular relation.
            database_name: database name.
        """
        self._update_relation_data(relation_id, {"database": database_name})

    def set_endpoints(self, relation_id: int, connection_strings: str) -> None:
        """Set database primary connections.

        This function writes in the application data bag, therefore,
        only the leader unit can call it.

        In VM charms, only the primary's address should be passed as an endpoint.
        In kubernetes charms, the service endpoint to the primary pod should be
        passed as an endpoint.

        Args:
            relation_id: the identifier for a particular relation.
            connection_strings: database hosts and ports comma separated list.
        """
        self._update_relation_data(relation_id, {"endpoints": connection_strings})

    def set_read_only_endpoints(self, relation_id: int, connection_strings: str) -> None:
        """Set database replicas connection strings.

        This function writes in the application data bag, therefore,
        only the leader unit can call it.

        Args:
            relation_id: the identifier for a particular relation.
            connection_strings: database hosts and ports comma separated list.
        """
        self._update_relation_data(relation_id, {"read-only-endpoints": connection_strings})

    def set_replset(self, relation_id: int, replset: str) -> None:
        """Set replica set name in the application relation databag.

        MongoDB only.

        Args:
            relation_id: the identifier for a particular relation.
            replset: replica set name.
        """
        self._update_relation_data(relation_id, {"replset": replset})

    def set_uris(self, relation_id: int, uris: str) -> None:
        """Set the database connection URIs in the application relation databag.

        MongoDB, Redis, and OpenSearch only.

        Args:
            relation_id: the identifier for a particular relation.
            uris: connection URIs.
        """
        self._update_relation_data(relation_id, {"uris": uris})

    def set_version(self, relation_id: int, version: str) -> None:
        """Set the database version in the application relation databag.

        Args:
            relation_id: the identifier for a particular relation.
            version: database version.
        """
        self._update_relation_data(relation_id, {"version": version})


class DatabaseRequires(DataRequires):
    """Requires-side of the database relation."""

    on = DatabaseRequiresEvents()

    def __init__(
        self,
        charm,
        relation_name: str,
        database_name: str,
        extra_user_roles: str = None,
        relations_aliases: List[str] = None,
    ):
        """Manager of database client relations."""
        super().__init__(charm, relation_name, extra_user_roles)
        self.database = database_name
        self.relations_aliases = relations_aliases

        # Define custom event names for each alias.
        if relations_aliases:
            # Ensure the number of aliases does not exceed the maximum
            # of connections allowed in the specific relation.
            relation_connection_limit = self.charm.meta.requires[relation_name].limit
            if len(relations_aliases) != relation_connection_limit:
                raise ValueError(
                    f"The number of aliases must match the maximum number of connections allowed in the relation. "
                    f"Expected {relation_connection_limit}, got {len(relations_aliases)}"
                )

            for relation_alias in relations_aliases:
                self.on.define_event(f"{relation_alias}_database_created", DatabaseCreatedEvent)
                self.on.define_event(
                    f"{relation_alias}_endpoints_changed", DatabaseEndpointsChangedEvent
                )
                self.on.define_event(
                    f"{relation_alias}_read_only_endpoints_changed",
                    DatabaseReadOnlyEndpointsChangedEvent,
                )

    def _assign_relation_alias(self, relation_id: int) -> None:
        """Assigns an alias to a relation.

        This function writes in the unit data bag.

        Args:
            relation_id: the identifier for a particular relation.
        """
        # If no aliases were provided, return immediately.
        if not self.relations_aliases:
            return

        # Return if an alias was already assigned to this relation
        # (like when there are more than one unit joining the relation).
        if (
            self.charm.model.get_relation(self.relation_name, relation_id)
            .data[self.local_unit]
            .get("alias")
        ):
            return

        # Retrieve the available aliases (the ones that weren't assigned to any relation).
        available_aliases = self.relations_aliases[:]
        for relation in self.charm.model.relations[self.relation_name]:
            alias = relation.data[self.local_unit].get("alias")
            if alias:
                logger.debug("Alias %s was already assigned to relation %d", alias, relation.id)
                available_aliases.remove(alias)

        # Set the alias in the unit relation databag of the specific relation.
        relation = self.charm.model.get_relation(self.relation_name, relation_id)
        relation.data[self.local_unit].update({"alias": available_aliases[0]})

    def _emit_aliased_event(self, event: RelationChangedEvent, event_name: str) -> None:
        """Emit an aliased event to a particular relation if it has an alias.

        Args:
            event: the relation changed event that was received.
            event_name: the name of the event to emit.
        """
        alias = self._get_relation_alias(event.relation.id)
        if alias:
            getattr(self.on, f"{alias}_{event_name}").emit(
                event.relation, app=event.app, unit=event.unit
            )

    def _get_relation_alias(self, relation_id: int) -> Optional[str]:
        """Returns the relation alias.

        Args:
            relation_id: the identifier for a particular relation.

        Returns:
            the relation alias or None if the relation was not found.
        """
        for relation in self.charm.model.relations[self.relation_name]:
            if relation.id == relation_id:
                return relation.data[self.local_unit].get("alias")
        return None

    def is_postgresql_plugin_enabled(self, plugin: str, relation_index: int = 0) -> bool:
        """Returns whether a plugin is enabled in the database.

        Args:
            plugin: name of the plugin to check.
            relation_index: optional relation index to check the database
                (default: 0 - first relation).

        PostgreSQL only.
        """
        # Psycopg 3 is imported locally to avoid the need of its package installation
        # when relating to a database charm other than PostgreSQL.
        import psycopg

        # Return False if no relation is established.
        if len(self.relations) == 0:
            return False

        relation_data = self.fetch_relation_data()[self.relations[relation_index].id]
        host = relation_data.get("endpoints")

        # Return False if there is no endpoint available.
        if host is None:
            return False

        host = host.split(":")[0]
        user = relation_data.get("username")
        password = relation_data.get("password")
        connection_string = (
            f"host='{host}' dbname='{self.database}' user='{user}' password='{password}'"
        )
        try:
            with psycopg.connect(connection_string) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(f"SELECT TRUE FROM pg_extension WHERE extname='{plugin}';")
                    return cursor.fetchone() is not None
        except psycopg.Error as e:
            logger.exception(
                f"failed to check whether {plugin} plugin is enabled in the database: %s", str(e)
            )
            return False

    def _on_relation_joined_event(self, event: RelationJoinedEvent) -> None:
        """Event emitted when the application joins the database relation."""
        # If relations aliases were provided, assign one to the relation.
        self._assign_relation_alias(event.relation.id)

        # Sets both database and extra user roles in the relation
        # if the roles are provided. Otherwise, sets only the database.
        if self.extra_user_roles:
            self._update_relation_data(
                event.relation.id,
                {
                    "database": self.database,
                    "extra-user-roles": self.extra_user_roles,
                },
            )
        else:
            self._update_relation_data(event.relation.id, {"database": self.database})

    def _on_relation_changed_event(self, event: RelationChangedEvent) -> None:
        """Event emitted when the database relation has changed."""
        # Check which data has changed to emit customs events.
        diff = self._diff(event)

        # Check if the database is created
        # (the database charm shared the credentials).
        if "username" in diff.added and "password" in diff.added:
            # Emit the default event (the one without an alias).
            logger.info("database created at %s", datetime.now())
            self.on.database_created.emit(event.relation, app=event.app, unit=event.unit)

            # Emit the aliased event (if any).
            self._emit_aliased_event(event, "database_created")

            # To avoid unnecessary application restarts do not trigger
            # “endpoints_changed“ event if “database_created“ is triggered.
            return

        # Emit an endpoints changed event if the database
        # added or changed this info in the relation databag.
        if "endpoints" in diff.added or "endpoints" in diff.changed:
            # Emit the default event (the one without an alias).
            logger.info("endpoints changed on %s", datetime.now())
            self.on.endpoints_changed.emit(event.relation, app=event.app, unit=event.unit)

            # Emit the aliased event (if any).
            self._emit_aliased_event(event, "endpoints_changed")

            # To avoid unnecessary application restarts do not trigger
            # “read_only_endpoints_changed“ event if “endpoints_changed“ is triggered.
            return

        # Emit a read only endpoints changed event if the database
        # added or changed this info in the relation databag.
        if "read-only-endpoints" in diff.added or "read-only-endpoints" in diff.changed:
            # Emit the default event (the one without an alias).
            logger.info("read-only-endpoints changed on %s", datetime.now())
            self.on.read_only_endpoints_changed.emit(
                event.relation, app=event.app, unit=event.unit
            )

            # Emit the aliased event (if any).
            self._emit_aliased_event(event, "read_only_endpoints_changed")


# Kafka related events


class KafkaProvidesEvent(RelationEvent):
    """Base class for Kafka events."""

    @property
    def topic(self) -> Optional[str]:
        """Returns the topic that was requested."""
        return self.relation.data[self.relation.app].get("topic")

    @property
    def consumer_group_prefix(self) -> Optional[str]:
        """Returns the consumer-group-prefix that was requested."""
        return self.relation.data[self.relation.app].get("consumer-group-prefix")


class TopicRequestedEvent(KafkaProvidesEvent, ExtraRoleEvent):
    """Event emitted when a new topic is requested for use on this relation."""


class KafkaProvidesEvents(CharmEvents):
    """Kafka events.

    This class defines the events that the Kafka can emit.
    """

    topic_requested = EventSource(TopicRequestedEvent)


class KafkaRequiresEvent(RelationEvent):
    """Base class for Kafka events."""

    @property
    def topic(self) -> Optional[str]:
        """Returns the topic."""
        return self.relation.data[self.relation.app].get("topic")

    @property
    def bootstrap_server(self) -> Optional[str]:
        """Returns a comma-separated list of broker uris."""
        return self.relation.data[self.relation.app].get("endpoints")

    @property
    def consumer_group_prefix(self) -> Optional[str]:
        """Returns the consumer-group-prefix."""
        return self.relation.data[self.relation.app].get("consumer-group-prefix")

    @property
    def zookeeper_uris(self) -> Optional[str]:
        """Returns a comma separated list of Zookeeper uris."""
        return self.relation.data[self.relation.app].get("zookeeper-uris")


class TopicCreatedEvent(AuthenticationEvent, KafkaRequiresEvent):
    """Event emitted when a new topic is created for use on this relation."""


class BootstrapServerChangedEvent(AuthenticationEvent, KafkaRequiresEvent):
    """Event emitted when the bootstrap server is changed."""


class KafkaRequiresEvents(CharmEvents):
    """Kafka events.

    This class defines the events that the Kafka can emit.
    """

    topic_created = EventSource(TopicCreatedEvent)
    bootstrap_server_changed = EventSource(BootstrapServerChangedEvent)


# Kafka Provides and Requires


class KafkaProvides(DataProvides):
    """Provider-side of the Kafka relation."""

    on = KafkaProvidesEvents()

    def __init__(self, charm: CharmBase, relation_name: str) -> None:
        super().__init__(charm, relation_name)

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Event emitted when the relation has changed."""
        # Only the leader should handle this event.
        if not self.local_unit.is_leader():
            return

        # Check which data has changed to emit customs events.
        diff = self._diff(event)

        # Emit a topic requested event if the setup key (topic name and optional
        # extra user roles) was added to the relation databag by the application.
        if "topic" in diff.added:
            self.on.topic_requested.emit(event.relation, app=event.app, unit=event.unit)

    def set_topic(self, relation_id: int, topic: str) -> None:
        """Set topic name in the application relation databag.

        Args:
            relation_id: the identifier for a particular relation.
            topic: the topic name.
        """
        self._update_relation_data(relation_id, {"topic": topic})

    def set_bootstrap_server(self, relation_id: int, bootstrap_server: str) -> None:
        """Set the bootstrap server in the application relation databag.

        Args:
            relation_id: the identifier for a particular relation.
            bootstrap_server: the bootstrap server address.
        """
        self._update_relation_data(relation_id, {"endpoints": bootstrap_server})

    def set_consumer_group_prefix(self, relation_id: int, consumer_group_prefix: str) -> None:
        """Set the consumer group prefix in the application relation databag.

        Args:
            relation_id: the identifier for a particular relation.
            consumer_group_prefix: the consumer group prefix string.
        """
        self._update_relation_data(relation_id, {"consumer-group-prefix": consumer_group_prefix})

    def set_zookeeper_uris(self, relation_id: int, zookeeper_uris: str) -> None:
        """Set the zookeeper uris in the application relation databag.

        Args:
            relation_id: the identifier for a particular relation.
            zookeeper_uris: comma-separated list of ZooKeeper server uris.
        """
        self._update_relation_data(relation_id, {"zookeeper-uris": zookeeper_uris})


class KafkaRequires(DataRequires):
    """Requires-side of the Kafka relation."""

    on = KafkaRequiresEvents()

    def __init__(
        self,
        charm,
        relation_name: str,
        topic: str,
        extra_user_roles: Optional[str] = None,
        consumer_group_prefix: Optional[str] = None,
    ):
        """Manager of Kafka client relations."""
        # super().__init__(charm, relation_name)
        super().__init__(charm, relation_name, extra_user_roles)
        self.charm = charm
        self.topic = topic
        self.consumer_group_prefix = consumer_group_prefix or ""

    def _on_relation_joined_event(self, event: RelationJoinedEvent) -> None:
        """Event emitted when the application joins the Kafka relation."""
        # Sets topic, extra user roles, and "consumer-group-prefix" in the relation
        relation_data = {
            f: getattr(self, f.replace("-", "_"), "")
            for f in ["consumer-group-prefix", "extra-user-roles", "topic"]
        }

        self._update_relation_data(event.relation.id, relation_data)

    def _on_relation_changed_event(self, event: RelationChangedEvent) -> None:
        """Event emitted when the Kafka relation has changed."""
        # Check which data has changed to emit customs events.
        diff = self._diff(event)

        # Check if the topic is created
        # (the Kafka charm shared the credentials).
        if "username" in diff.added and "password" in diff.added:
            # Emit the default event (the one without an alias).
            logger.info("topic created at %s", datetime.now())
            self.on.topic_created.emit(event.relation, app=event.app, unit=event.unit)

            # To avoid unnecessary application restarts do not trigger
            # “endpoints_changed“ event if “topic_created“ is triggered.
            return

        # Emit an endpoints (bootstrap-server) changed event if the Kafka endpoints
        # added or changed this info in the relation databag.
        if "endpoints" in diff.added or "endpoints" in diff.changed:
            # Emit the default event (the one without an alias).
            logger.info("endpoints changed on %s", datetime.now())
            self.on.bootstrap_server_changed.emit(
                event.relation, app=event.app, unit=event.unit
            )  # here check if this is the right design
            return


# Opensearch related events


class OpenSearchProvidesEvent(RelationEvent):
    """Base class for OpenSearch events."""

    @property
    def index(self) -> Optional[str]:
        """Returns the index that was requested."""
        return self.relation.data[self.relation.app].get("index")


class IndexRequestedEvent(OpenSearchProvidesEvent, ExtraRoleEvent):
    """Event emitted when a new index is requested for use on this relation."""


class OpenSearchProvidesEvents(CharmEvents):
    """OpenSearch events.

    This class defines the events that OpenSearch can emit.
    """

    index_requested = EventSource(IndexRequestedEvent)


class OpenSearchRequiresEvent(DatabaseRequiresEvent):
    """Base class for OpenSearch requirer events."""


class IndexCreatedEvent(AuthenticationEvent, OpenSearchRequiresEvent):
    """Event emitted when a new index is created for use on this relation."""


class OpenSearchRequiresEvents(CharmEvents):
    """OpenSearch events.

    This class defines the events that the opensearch requirer can emit.
    """

    index_created = EventSource(IndexCreatedEvent)
    endpoints_changed = EventSource(DatabaseEndpointsChangedEvent)
    authentication_updated = EventSource(AuthenticationEvent)


# OpenSearch Provides and Requires Objects


class OpenSearchProvides(DataProvides):
    """Provider-side of the OpenSearch relation."""

    on = OpenSearchProvidesEvents()

    def __init__(self, charm: CharmBase, relation_name: str) -> None:
        super().__init__(charm, relation_name)

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """Event emitted when the relation has changed."""
        # Only the leader should handle this event.
        if not self.local_unit.is_leader():
            return

        # Check which data has changed to emit customs events.
        diff = self._diff(event)

        # Emit an index requested event if the setup key (index name and optional extra user roles)
        # have been added to the relation databag by the application.
        if "index" in diff.added:
            self.on.index_requested.emit(event.relation, app=event.app, unit=event.unit)

    def set_index(self, relation_id: int, index: str) -> None:
        """Set the index in the application relation databag.

        Args:
            relation_id: the identifier for a particular relation.
            index: the index as it is _created_ on the provider charm. This needn't match the
                requested index, and can be used to present a different index name if, for example,
                the requested index is invalid.
        """
        self._update_relation_data(relation_id, {"index": index})

    def set_endpoints(self, relation_id: int, endpoints: str) -> None:
        """Set the endpoints in the application relation databag.

        Args:
            relation_id: the identifier for a particular relation.
            endpoints: the endpoint addresses for opensearch nodes.
        """
        self._update_relation_data(relation_id, {"endpoints": endpoints})

    def set_version(self, relation_id: int, version: str) -> None:
        """Set the opensearch version in the application relation databag.

        Args:
            relation_id: the identifier for a particular relation.
            version: database version.
        """
        self._update_relation_data(relation_id, {"version": version})


class OpenSearchRequires(DataRequires):
    """Requires-side of the OpenSearch relation."""

    on = OpenSearchRequiresEvents()

    def __init__(
        self, charm, relation_name: str, index: str, extra_user_roles: Optional[str] = None
    ):
        """Manager of OpenSearch client relations."""
        super().__init__(charm, relation_name, extra_user_roles)
        self.charm = charm
        self.index = index

    def _on_relation_joined_event(self, event: RelationJoinedEvent) -> None:
        """Event emitted when the application joins the OpenSearch relation."""
        # Sets both index and extra user roles in the relation if the roles are provided.
        # Otherwise, sets only the index.
        data = {"index": self.index}
        if self.extra_user_roles:
            data["extra-user-roles"] = self.extra_user_roles

        self._update_relation_data(event.relation.id, data)

    def _on_relation_changed_event(self, event: RelationChangedEvent) -> None:
        """Event emitted when the OpenSearch relation has changed.

        This event triggers individual custom events depending on the changing relation.
        """
        # Check which data has changed to emit customs events.
        diff = self._diff(event)

        # Check if authentication has updated, emit event if so
        updates = {"username", "password", "tls", "tls-ca"}
        if len(set(diff._asdict().keys()) - updates) < len(diff):
            logger.info("authentication updated at: %s", datetime.now())
            self.on.authentication_updated.emit(event.relation, app=event.app, unit=event.unit)

        # Check if the index is created
        # (the OpenSearch charm shares the credentials).
        if "username" in diff.added and "password" in diff.added:
            # Emit the default event (the one without an alias).
            logger.info("index created at: %s", datetime.now())
            self.on.index_created.emit(event.relation, app=event.app, unit=event.unit)

            # To avoid unnecessary application restarts do not trigger
            # “endpoints_changed“ event if “index_created“ is triggered.
            return

        # Emit a endpoints changed event if the OpenSearch application added or changed this info
        # in the relation databag.
        if "endpoints" in diff.added or "endpoints" in diff.changed:
            # Emit the default event (the one without an alias).
            logger.info("endpoints changed on %s", datetime.now())
            self.on.endpoints_changed.emit(
                event.relation, app=event.app, unit=event.unit
            )  # here check if this is the right design
            return
