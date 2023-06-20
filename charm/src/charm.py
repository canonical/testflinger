#!/usr/bin/env python3
# Copyright 2023 Paul Larson
# See LICENSE file for licensing details.

import logging
import ops
import sys

from ops.pebble import Layer
from charms.data_platform_libs.v0.data_interfaces import DatabaseCreatedEvent
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route

logger = logging.getLogger(__name__)


class TestflingerCharm(ops.CharmBase):
    """Testflinger charm"""

    _stored = ops.framework.StoredState()

    def __init__(self, *args):
        """Initialize the charm"""
        super().__init__(*args)
        self.pebble_service_name = "testflinger"
        self.container = self.unit.get_container("testflinger")
        self._stored.set_default(
            reldata={},
        )

        self._require_nginx_route()

        self.mongodb = DatabaseRequires(
            self,
            relation_name="mongodb_client",
            database_name="testflinger_db",
        )

        self.framework.observe(
            self.mongodb.on.database_created,
            self._on_mongodb_client_relation_changed,
        )
        self.framework.observe(
            self.mongodb.on.endpoints_changed,
            self._on_mongodb_client_relation_changed,
        )
        self.framework.observe(
            self.on.mongodb_client_relation_broken,
            self._on_mongodb_client_relation_removed,
        )
        self.framework.observe(
            self.on.testflinger_pebble_ready, self._on_testflinger_pebble_ready
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    @property
    def version(self) -> str:
        """Report the current version of the app"""
        # TODO: get the version somehow and return it
        return "Version ?"

    def _require_nginx_route(self):
        require_nginx_route(
            charm=self,
            service_hostname=self.config["external_hostname"],
            service_name=self.app.name,
            service_port=5000,
        )

    def _on_testflinger_pebble_ready(
        self, event: ops.PebbleReadyEvent
    ) -> None:
        """Handle pebble-ready event."""
        container = event.workload
        container.add_layer("testflinger", self._pebble_layer, combine=True)
        container.replan()
        self.unit.status = ops.ActiveStatus()

    def _on_mongodb_client_relation_changed(
        self, event: DatabaseCreatedEvent
    ) -> None:
        """Event is fired when mongodb database is created."""
        if "mongodb" not in self._stored.reldata:
            self._stored.reldata["mongodb"] = {}

        initial = dict(self._stored.reldata["mongodb"])
        self._stored.reldata["mongodb"].update(
            self.mongodb.fetch_relation_data()[event.relation.id]
        )
        if initial != self._stored.reldata["mongodb"]:
            self._update_layer_and_restart(None)

    def _update_layer_and_restart(self, event) -> None:
        """Define and start layer for testflinger using Pebble"""
        if not self.container.can_connect():
            self.unit.status = ops.WaitingStatus(
                "Waiting for Pebble in workload container"
            )
            return

        self.unit.status = ops.MaintenanceStatus("Assembling pod spec")
        new_layer = self._pebble_layer.to_dict()

        # Get the current pebble layer config
        services = self.container.get_plan().to_dict().get("services", {})
        if services != new_layer["services"]:
            # Changes were made, add the new layer
            self.container.add_layer(
                "testflinger", self._pebble_layer, combine=True
            )
            logger.info("Added updated layer 'testflinger' to Pebble plan")

            self.container.restart(self.pebble_service_name)
            logger.info("Restarted '%s' service", self.pebble_service_name)

        # add workload version in juju status
        self.unit.set_workload_version(self.version)
        self.unit.status = ops.ActiveStatus()

    def _on_mongodb_client_relation_removed(
        self, event: ops.framework.EventBase
    ) -> None:
        """Event is fired when relation with mongodb is broken."""
        self.unit.status = ops.WaitingStatus("Waiting for database relation")
        sys.exit()

    def _on_config_changed(self, event: ops.framework.EventBase) -> None:
        """Handle config changed event"""
        self._update_layer_and_restart(event)

    @property
    def _pebble_layer(self):
        """Return a dictionary representing a Pebble layer."""
        command = " ".join(
            [
                "gunicorn",
                "--bind",
                "0.0.0.0:5000",
                "testflinger:app",
            ]
        )
        pebble_layer = {
            "summary": "Testflinger server",
            "description": "pebble config layer for Testflinger server",
            "services": {
                self.pebble_service_name: {
                    "override": "replace",
                    "summary": "testflinger",
                    "command": command,
                    "startup": "enabled",
                    "environment": self.app_environment,
                }
            },
        }
        return Layer(pebble_layer)

    @property
    def app_environment(self) -> dict:
        """Get dict of env data for the mongodb credentials"""
        db_data = self.fetch_mongodb_relation_data()
        env = {
            "MONGODB_HOST": db_data.get("db_host"),
            "MONGODB_PORT": db_data.get("db_port"),
            "MONGODB_USERNAME": db_data.get("db_username"),
            "MONGODB_PASSWORD": db_data.get("db_password"),
            "MONGODB_DATABASE": db_data.get("db_database"),
        }
        return env

    def fetch_mongodb_relation_data(self) -> dict:
        """Get relation data from the mongodb charm"""
        data = self._stored.reldata.get("mongodb", {})
        logger.debug("Got following database data: %s", data)
        if not data:
            self.unit.status = ops.WaitingStatus(
                "Waiting for database relation"
            )
            raise SystemExit(0)

        if ":" in data.get("endpoints"):
            host, port = data.get("endpoints").split(":")
        else:
            host = data.get("endpoints")
            port = "27017"

        db_data = {
            "db_host": host,
            "db_port": port,
            "db_username": data.get("username"),
            "db_password": data.get("password"),
            "db_database": data.get("database"),
        }
        return db_data


if __name__ == "__main__":
    ops.main(TestflingerCharm)
