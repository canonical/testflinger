#!/usr/bin/env python3
# Copyright (C) 2023 Canonical
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
#
"""Testflinger Juju charm."""

import logging
import sys

import bcrypt
import ops
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseRequires,
)
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from ops.main import main
from ops.pebble import Layer
from pymongo import MongoClient
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

TESTFLINGER_ADMIN_ID = "testflinger-admin"


class TestflingerCharm(ops.CharmBase):
    """Testflinger charm."""

    __test__ = False
    """Prevents pytest from trying to run this class as a test."""

    _stored = ops.framework.StoredState()

    def __init__(self, *args):
        """Initialize the charm."""
        super().__init__(*args)
        self.pebble_service_name = "testflinger"
        self.pebble_check_name = "v1_up"
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

        self._prometheus_scraping = MetricsEndpointProvider(
            self,
            relation_name="metrics-endpoint",
            jobs=[{"static_configs": [{"targets": ["*:5000"]}]}],
            refresh_event=self.on.config_changed,
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
        self.framework.observe(
            self.on.set_admin_password_action, self.on_set_admin_password
        )

    @property
    def version(self) -> str:
        """Report the current version of the app."""
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
            self._update_layer_and_restart()

    def _update_layer_and_restart(self) -> None:
        """Define and start layer for testflinger using Pebble."""
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
        self, _: ops.framework.EventBase
    ) -> None:
        """
        Event is fired when relation with mongodb is broken.
        We need to accept the event as an argument, but we don't use it.
        """
        self.unit.status = ops.WaitingStatus("Waiting for database relation")
        sys.exit()

    def _on_config_changed(self, _: ops.framework.EventBase) -> None:
        """
        Handle config changed event
        We need to accept the event as an argument, but we don't use it.
        """
        self._update_layer_and_restart()

    @property
    def _pebble_layer(self):
        """Return a dictionary representing a Pebble layer."""
        keepalive = str(self.config["keepalive"])
        command = " ".join(
            [
                "gunicorn",
                "-k",
                "gevent",
                "--keep-alive",
                keepalive,
                "--bind",
                "0.0.0.0:5000",
                "app:app",
                "--access-logfile",
                "-",
                "--error-logfile",
                "-",
            ]
        )
        pebble_layer = {
            "summary": "Testflinger server",
            "description": "pebble config layer for Testflinger server",
            "checks": {
                self.pebble_check_name: {
                    "override": "replace",
                    "period": "10s",
                    "timeout": "3s",
                    "threshold": 5,
                    "http": {
                        "url": "http://0.0.0.0:5000/v1/",
                    },
                }
            },
            "services": {
                self.pebble_service_name: {
                    "override": "replace",
                    "summary": "testflinger",
                    "command": command,
                    "startup": "enabled",
                    "environment": self.app_environment,
                    "on-check-failure": {
                        self.pebble_check_name: "restart",
                    },
                }
            },
        }
        return Layer(pebble_layer)

    @property
    def app_environment(self) -> dict:
        """
        Get dict of env data for the mongodb credentials
        and other config variables.
        """
        db_data = self.fetch_mongodb_relation_data()
        env = {
            "MONGODB_HOST": db_data.get("db_host"),
            "MONGODB_PORT": db_data.get("db_port"),
            "MONGODB_USERNAME": db_data.get("db_username"),
            "MONGODB_PASSWORD": db_data.get("db_password"),
            "MONGODB_DATABASE": db_data.get("db_database"),
            "MONGODB_MAX_POOL_SIZE": str(self.config["max_pool_size"]),
            "JWT_SIGNING_KEY": self.config["jwt_signing_key"],
            "HTTP_PROXY": self.config["http_proxy"],
            "HTTPS_PROXY": self.config["https_proxy"],
            "NO_PROXY": self.config["no_proxy"],
        }
        return env

    def fetch_mongodb_relation_data(self) -> dict:
        """Get relation data from the mongodb charm."""
        data = self.mongodb.fetch_relation_data()
        logger.debug("Got following database data: %s", data)
        if not data:
            self.unit.status = ops.WaitingStatus(
                "Waiting for database relation"
            )
            sys.exit()

        for val in data.values():
            if not val:
                continue
            if ":" in val.get("endpoints"):
                host, port = val.get("endpoints").split(":")
            else:
                host = val.get("endpoints")
                port = "27017"
            username = val.get("username")
            password = val.get("password")
            database = val.get("database")
            break
        else:
            logger.error("No database relation data found yet")
            sys.exit()

        db_data = {
            "db_host": host,
            "db_port": port,
            "db_username": username,
            "db_password": password,
            "db_database": database,
        }
        return db_data

    def on_set_admin_password(self, event: ops.ActionEvent):
        """Update or set admin password to admin user."""
        # Do not perform action if we are not application leader
        if not self.unit.is_leader():
            event.fail("Action can only be executed on leader unit")
            return

        admin_secret = event.params.get("password")
        if not admin_secret:
            event.fail("Password parameter is required")
            return

        try:
            db = self.connect_to_mongodb()
            if db is None:
                event.fail("Unable to connect to MongoDB")
                return

            admin_secret_hash = bcrypt.hashpw(
                admin_secret.encode("utf-8"), bcrypt.gensalt()
            ).decode()

            if self.check_client_exist(db):
                # Update existing admin user to rotate its password
                db.client_permissions.update_one(
                    {"client_id": TESTFLINGER_ADMIN_ID},
                    {"$set": {"client_secret_hash": admin_secret_hash}},
                )
                event.set_results(
                    {"result": "Admin password updated successfully"}
                )
            else:
                # Create new admin user
                db.client_permissions.insert_one(
                    {
                        "client_id": TESTFLINGER_ADMIN_ID,
                        "client_secret_hash": admin_secret_hash,
                        "role": "admin",
                    }
                )
                event.set_results(
                    {"result": "Admin user created successfully"}
                )

        except PyMongoError as e:
            logger.error("MongoDB operation failed: %s", str(e))
            event.fail(f"MongoDB operation failed: {str(e)}")

    def connect_to_mongodb(self):
        """Get Mongo credentials from relation data and setup connection."""
        # Determine if we are already connected to database
        db_relation = self.model.get_relation("mongodb_client")
        if not db_relation:
            return

        # Get the relation data from the remote application
        for unit in db_relation.units:
            remote_app = unit.app
            remote_app_databag = db_relation.data[remote_app]
            if "uris" in remote_app_databag:
                mongo_client = MongoClient(host=remote_app_databag["uris"])
                return mongo_client[remote_app_databag["database"]]

        return None

    def check_client_exist(self, db: MongoClient):
        """Validate if client_id already exists in collection."""
        return (
            db.client_permissions.count_documents(
                {"client_id": TESTFLINGER_ADMIN_ID}, limit=1
            )
            != 0
        )


if __name__ == "__main__":
    main(TestflingerCharm)
