# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

r"""## Overview.

This library can be used to manage the cos_agent relation interface:

- `COSAgentProvider`: Use in machine charms that need to have a workload's metrics
  or logs scraped, or forward rule files or dashboards to Prometheus, Loki or Grafana through
  the Grafana Agent machine charm.
  NOTE: Be sure to add `limit: 1` in your charm for the cos-agent relation. That is the only
   way we currently have to prevent two different grafana agent apps deployed on the same VM.

- `COSAgentConsumer`: Used in the Grafana Agent machine charm to manage the requirer side of
  the `cos_agent` interface.


## COSAgentProvider Library Usage

Grafana Agent machine Charmed Operator interacts with its clients using the cos_agent library.
Charms seeking to send telemetry, must do so using the `COSAgentProvider` object from
this charm library.

Using the `COSAgentProvider` object only requires instantiating it,
typically in the `__init__` method of your charm (the one which sends telemetry).


```python
    def __init__(
        self,
        charm: CharmType,
        relation_name: str = DEFAULT_RELATION_NAME,
        metrics_endpoints: Optional[List[_MetricsEndpointDict]] = None,
        metrics_rules_dir: str = "./src/prometheus_alert_rules",
        logs_rules_dir: str = "./src/loki_alert_rules",
        recurse_rules_dirs: bool = False,
        log_slots: Optional[List[str]] = None,
        dashboard_dirs: Optional[List[str]] = None,
        refresh_events: Optional[List] = None,
        tracing_protocols: Optional[List[str]] = None,
        scrape_configs: Optional[Union[List[Dict], Callable]] = None,
    ):
```

### Parameters

- `charm`: The instance of the charm that instantiates `COSAgentProvider`, typically `self`.

- `relation_name`: If your charmed operator uses a relation name other than `cos-agent` to use
    the `cos_agent` interface, this is where you have to specify that.

- `metrics_endpoints`: In this parameter you can specify the metrics endpoints that Grafana Agent
    machine Charmed Operator will scrape. The configs of this list will be merged with the configs
    from `scrape_configs`.

- `metrics_rules_dir`: The directory in which the Charmed Operator stores its metrics alert rules
  files.

- `logs_rules_dir`: The directory in which the Charmed Operator stores its logs alert rules files.

- `recurse_rules_dirs`: This parameters set whether Grafana Agent machine Charmed Operator has to
  search alert rules files recursively in the previous two directories or not.

- `log_slots`: Snap slots to connect to for scraping logs in the form ["snap-name:slot", ...].

- `dashboard_dirs`: List of directories where the dashboards are stored in the Charmed Operator.

- `refresh_events`: List of events on which to refresh relation data.

- `tracing_protocols`: List of requested tracing protocols that the charm requires to send traces.

- `scrape_configs`: List of standard scrape_configs dicts or a callable that returns the list in
    case the configs need to be generated dynamically. The contents of this list will be merged
    with the configs from `metrics_endpoints`.


### Example 1 - Minimal instrumentation:

In order to use this object the following should be in the `charm.py` file.

```python
from charms.grafana_agent.v0.cos_agent import COSAgentProvider
...
class TelemetryProviderCharm(CharmBase):
    def __init__(self, *args):
        ...
        self._grafana_agent = COSAgentProvider(self)
```

### Example 2 - Full instrumentation:

In order to use this object the following should be in the `charm.py` file.

```python
from charms.grafana_agent.v0.cos_agent import COSAgentProvider
...
class TelemetryProviderCharm(CharmBase):
    def __init__(self, *args):
        ...
        self._grafana_agent = COSAgentProvider(
            self,
            relation_name="custom-cos-agent",
            metrics_endpoints=[
                # specify "path" and "port" to scrape from localhost
                {"path": "/metrics", "port": 9000},
                {"path": "/metrics", "port": 9001},
                {"path": "/metrics", "port": 9002},
            ],
            metrics_rules_dir="./src/alert_rules/prometheus",
            logs_rules_dir="./src/alert_rules/loki",
            recursive_rules_dir=True,
            log_slots=["my-app:slot"],
            dashboard_dirs=["./src/dashboards_1", "./src/dashboards_2"],
            refresh_events=["update-status", "upgrade-charm"],
            tracing_protocols=["otlp_http", "otlp_grpc"],
            scrape_configs=[
                {
                    "job_name": "custom_job",
                    "metrics_path": "/metrics",
                    "authorization": {"credentials": "bearer-token"},
                    "static_configs": [
                        {
                            "targets": ["localhost:9003"]},
                            "labels": {"key": "value"},
                        },
                    ],
                },
            ]
        )
```

### Example 3 - Dynamic scrape configs generation:

Pass a function to the `scrape_configs` to decouple the generation of the configs
from the instantiation of the COSAgentProvider object.

```python
from charms.grafana_agent.v0.cos_agent import COSAgentProvider
...

class TelemetryProviderCharm(CharmBase):
    def generate_scrape_configs(self):
        return [
            {
                "job_name": "custom",
                "metrics_path": "/metrics",
                "static_configs": [{"targets": ["localhost:9000"]}],
            },
        ]

    def __init__(self, *args):
        ...
        self._grafana_agent = COSAgentProvider(
            self,
            scrape_configs=self.generate_scrape_configs,
        )
```

## COSAgentConsumer Library Usage

This object may be used by any Charmed Operator which gathers telemetry data by
implementing the consumer side of the `cos_agent` interface.
For instance Grafana Agent machine Charmed Operator.

For this purpose the charm needs to instantiate the `COSAgentConsumer` object with one mandatory
and two optional arguments.

### Parameters

- `charm`: A reference to the parent (Grafana Agent machine) charm.

- `relation_name`: The name of the relation that the charm uses to interact
  with its clients that provides telemetry data using the `COSAgentProvider` object.

  If provided, this relation name must match a provided relation in metadata.yaml with the
  `cos_agent` interface.
  The default value of this argument is "cos-agent".

- `refresh_events`: List of events on which to refresh relation data.


### Example 1 - Minimal instrumentation:

In order to use this object the following should be in the `charm.py` file.

```python
from charms.grafana_agent.v0.cos_agent import COSAgentConsumer
...
class GrafanaAgentMachineCharm(GrafanaAgentCharm)
    def __init__(self, *args):
        ...
        self._cos = COSAgentRequirer(self)
```


### Example 2 - Full instrumentation:

In order to use this object the following should be in the `charm.py` file.

```python
from charms.grafana_agent.v0.cos_agent import COSAgentConsumer
...
class GrafanaAgentMachineCharm(GrafanaAgentCharm)
    def __init__(self, *args):
        ...
        self._cos = COSAgentRequirer(
            self,
            relation_name="cos-agent-consumer",
            refresh_events=["update-status", "upgrade-charm"],
        )
```
"""

import enum
import json
import logging
import socket
from collections import namedtuple
from itertools import chain
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Literal,
    MutableMapping,
    Optional,
    Set,
    Tuple,
    Union,
)

import pydantic
from cosl import DashboardPath40UID, JujuTopology, LZMABase64
from cosl.rules import AlertRules, generic_alert_groups
from ops.charm import RelationChangedEvent
from ops.framework import EventBase, EventSource, Object, ObjectEvents
from ops.model import ModelError, Relation
from ops.testing import CharmType

if TYPE_CHECKING:
    try:
        from typing import TypedDict

        class _MetricsEndpointDict(TypedDict):
            path: str
            port: int

    except ModuleNotFoundError:
        _MetricsEndpointDict = Dict  # pyright: ignore

LIBID = "dc15fa84cef84ce58155fb84f6c6213a"
LIBAPI = 0
LIBPATCH = 22

PYDEPS = ["cosl >= 0.0.50", "pydantic"]

DEFAULT_RELATION_NAME = "cos-agent"
DEFAULT_PEER_RELATION_NAME = "peers"

logger = logging.getLogger(__name__)
SnapEndpoint = namedtuple("SnapEndpoint", "owner, name")

# Note: MutableMapping is imported from the typing module and not collections.abc
# because subscripting collections.abc.MutableMapping was added in python 3.9, but
# most of our charms are based on 20.04, which has python 3.8.

_RawDatabag = MutableMapping[str, str]


class TransportProtocolType(str, enum.Enum):
    """Receiver Type."""

    http = "http"
    grpc = "grpc"


receiver_protocol_to_transport_protocol = {
    "zipkin": TransportProtocolType.http,
    "kafka": TransportProtocolType.http,
    "tempo_http": TransportProtocolType.http,
    "tempo_grpc": TransportProtocolType.grpc,
    "otlp_grpc": TransportProtocolType.grpc,
    "otlp_http": TransportProtocolType.http,
    "jaeger_thrift_http": TransportProtocolType.http,
}

_tracing_receivers_ports = {
    # OTLP receiver: see
    #   https://github.com/open-telemetry/opentelemetry-collector/tree/v0.96.0/receiver/otlpreceiver
    "otlp_http": 4318,
    "otlp_grpc": 4317,
    # Jaeger receiver: see
    #   https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/v0.96.0/receiver/jaegerreceiver
    "jaeger_grpc": 14250,
    "jaeger_thrift_http": 14268,
    # Zipkin receiver: see
    #   https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/v0.96.0/receiver/zipkinreceiver
    "zipkin": 9411,
}

ReceiverProtocol = Literal["otlp_grpc", "otlp_http", "zipkin", "jaeger_thrift_http", "jaeger_grpc"]


class TracingError(Exception):
    """Base class for custom errors raised by tracing."""


class NotReadyError(TracingError):
    """Raised by the provider wrapper if a requirer hasn't published the required data (yet)."""


class ProtocolNotFoundError(TracingError):
    """Raised if the user doesn't receive an endpoint for a protocol it requested."""


class ProtocolNotRequestedError(ProtocolNotFoundError):
    """Raised if the user attempts to obtain an endpoint for a protocol it did not request."""


class DataValidationError(TracingError):
    """Raised when data validation fails on IPU relation data."""


class AmbiguousRelationUsageError(TracingError):
    """Raised when one wrongly assumes that there can only be one relation on an endpoint."""


# TODO we want to eventually use `DatabagModel` from cosl but it likely needs a move to common package first
if int(pydantic.version.VERSION.split(".")[0]) < 2:  # type: ignore

    class DatabagModel(pydantic.BaseModel):  # type: ignore
        """Base databag model."""

        class Config:
            """Pydantic config."""

            # ignore any extra fields in the databag
            extra = "ignore"
            """Ignore any extra fields in the databag."""
            allow_population_by_field_name = True
            """Allow instantiating this class by field name (instead of forcing alias)."""

        _NEST_UNDER = None

        @classmethod
        def load(cls, databag: MutableMapping):
            """Load this model from a Juju databag."""
            if cls._NEST_UNDER:
                return cls.parse_obj(json.loads(databag[cls._NEST_UNDER]))

            try:
                data = {
                    k: json.loads(v)
                    for k, v in databag.items()
                    # Don't attempt to parse model-external values
                    if k in {f.alias for f in cls.__fields__.values()}
                }
            except json.JSONDecodeError as e:
                msg = f"invalid databag contents: expecting json. {databag}"
                logger.error(msg)
                raise DataValidationError(msg) from e

            try:
                return cls.parse_raw(json.dumps(data))  # type: ignore
            except pydantic.ValidationError as e:
                msg = f"failed to validate databag: {databag}"
                logger.debug(msg, exc_info=True)
                raise DataValidationError(msg) from e

        def dump(self, databag: Optional[MutableMapping] = None, clear: bool = True):
            """Write the contents of this model to Juju databag.

            :param databag: the databag to write the data to.
            :param clear: ensure the databag is cleared before writing it.
            """
            if clear and databag:
                databag.clear()

            if databag is None:
                databag = {}

            if self._NEST_UNDER:
                databag[self._NEST_UNDER] = self.json(by_alias=True)
                return databag

            dct = self.dict()
            for key, field in self.__fields__.items():  # type: ignore
                value = dct[key]
                databag[field.alias or key] = json.dumps(value)

            return databag

else:
    from pydantic import ConfigDict

    class DatabagModel(pydantic.BaseModel):
        """Base databag model."""

        model_config = ConfigDict(
            # ignore any extra fields in the databag
            extra="ignore",
            # Allow instantiating this class by field name (instead of forcing alias).
            populate_by_name=True,
            # Custom config key: whether to nest the whole datastructure (as json)
            # under a field or spread it out at the toplevel.
            _NEST_UNDER=None,  # type: ignore
            arbitrary_types_allowed=True,
        )
        """Pydantic config."""

        @classmethod
        def load(cls, databag: MutableMapping):
            """Load this model from a Juju databag."""
            nest_under = cls.model_config.get("_NEST_UNDER")  # type: ignore
            if nest_under:
                return cls.model_validate(json.loads(databag[nest_under]))  # type: ignore

            try:
                data = {
                    k: json.loads(v)
                    for k, v in databag.items()
                    # Don't attempt to parse model-external values
                    if k in {(f.alias or n) for n, f in cls.__fields__.items()}
                }
            except json.JSONDecodeError as e:
                msg = f"invalid databag contents: expecting json. {databag}"
                logger.error(msg)
                raise DataValidationError(msg) from e

            try:
                return cls.model_validate_json(json.dumps(data))  # type: ignore
            except pydantic.ValidationError as e:
                msg = f"failed to validate databag: {databag}"
                logger.debug(msg, exc_info=True)
                raise DataValidationError(msg) from e

        def dump(self, databag: Optional[MutableMapping] = None, clear: bool = True):
            """Write the contents of this model to Juju databag.

            :param databag: the databag to write the data to.
            :param clear: ensure the databag is cleared before writing it.
            """
            if clear and databag:
                databag.clear()

            if databag is None:
                databag = {}
            nest_under = self.model_config.get("_NEST_UNDER")
            if nest_under:
                databag[nest_under] = self.model_dump_json(  # type: ignore
                    by_alias=True,
                    # skip keys whose values are default
                    exclude_defaults=True,
                )
                return databag

            dct = self.model_dump()  # type: ignore
            for key, field in self.model_fields.items():  # type: ignore
                value = dct[key]
                if value == field.default:
                    continue
                databag[field.alias or key] = json.dumps(value)

            return databag


class CosAgentProviderUnitData(DatabagModel):  # type: ignore
    """Unit databag model for `cos-agent` relation."""

    # The following entries are the same for all units of the same principal.
    # Note that the same grafana agent subordinate may be related to several apps.
    # this needs to make its way to the gagent leader
    metrics_alert_rules: dict
    log_alert_rules: dict
    dashboards: List[str]
    # subordinate is no longer used but we should keep it until we bump the library to ensure
    # we don't break compatibility.
    subordinate: Optional[bool] = None

    # The following entries may vary across units of the same principal app.
    # this data does not need to be forwarded to the gagent leader
    metrics_scrape_jobs: List[Dict]
    log_slots: List[str]

    # Requested tracing protocols.
    tracing_protocols: Optional[List[str]] = None

    # when this whole datastructure is dumped into a databag, it will be nested under this key.
    # while not strictly necessary (we could have it 'flattened out' into the databag),
    # this simplifies working with the model.
    KEY: ClassVar[str] = "config"


class CosAgentPeersUnitData(DatabagModel):  # type: ignore
    """Unit databag model for `peers` cos-agent machine charm peer relation."""

    # We need the principal unit name and relation metadata to be able to render identifiers
    # (e.g. topology) on the leader side, after all the data moves into peer data (the grafana
    # agent leader can only see its own principal, because it is a subordinate charm).
    unit_name: str
    relation_id: str
    relation_name: str

    # The only data that is forwarded to the leader is data that needs to go into the app databags
    # of the outgoing o11y relations.
    metrics_alert_rules: Optional[dict]
    log_alert_rules: Optional[dict]
    dashboards: Optional[List[str]]

    # when this whole datastructure is dumped into a databag, it will be nested under this key.
    # while not strictly necessary (we could have it 'flattened out' into the databag),
    # this simplifies working with the model.
    KEY: ClassVar[str] = "config"

    @property
    def app_name(self) -> str:
        """Parse out the app name from the unit name.

        TODO: Switch to using `model_post_init` when pydantic v2 is released?
          https://github.com/pydantic/pydantic/issues/1729#issuecomment-1300576214
        """
        return self.unit_name.split("/")[0]


if int(pydantic.version.VERSION.split(".")[0]) < 2:  # type: ignore

    class ProtocolType(pydantic.BaseModel):  # type: ignore
        """Protocol Type."""

        class Config:
            """Pydantic config."""

            use_enum_values = True
            """Allow serializing enum values."""

        name: str = pydantic.Field(
            ...,
            description="Receiver protocol name. What protocols are supported (and what they are called) "
            "may differ per provider.",
            examples=["otlp_grpc", "otlp_http", "tempo_http"],
        )

        type: TransportProtocolType = pydantic.Field(
            ...,
            description="The transport protocol used by this receiver.",
            examples=["http", "grpc"],
        )

else:

    class ProtocolType(pydantic.BaseModel):
        """Protocol Type."""

        model_config = pydantic.ConfigDict(
            # Allow serializing enum values.
            use_enum_values=True
        )
        """Pydantic config."""

        name: str = pydantic.Field(
            ...,
            description="Receiver protocol name. What protocols are supported (and what they are called) "
            "may differ per provider.",
            examples=["otlp_grpc", "otlp_http", "tempo_http"],
        )

        type: TransportProtocolType = pydantic.Field(
            ...,
            description="The transport protocol used by this receiver.",
            examples=["http", "grpc"],
        )


class Receiver(pydantic.BaseModel):
    """Specification of an active receiver."""

    protocol: ProtocolType = pydantic.Field(..., description="Receiver protocol name and type.")
    url: Optional[str] = pydantic.Field(
        ...,
        description="""URL at which the receiver is reachable. If there's an ingress, it would be the external URL.
        Otherwise, it would be the service's fqdn or internal IP.
        If the protocol type is grpc, the url will not contain a scheme.""",
        examples=[
            "http://traefik_address:2331",
            "https://traefik_address:2331",
            "http://tempo_public_ip:2331",
            "https://tempo_public_ip:2331",
            "tempo_public_ip:2331",
        ],
    )


class CosAgentRequirerUnitData(DatabagModel):  # type: ignore
    """Application databag model for the COS-agent requirer."""

    receivers: List[Receiver] = pydantic.Field(
        ...,
        description="List of all receivers enabled on the tracing provider.",
    )


class COSAgentProvider(Object):
    """Integration endpoint wrapper for the provider side of the cos_agent interface."""

    def __init__(
        self,
        charm: CharmType,
        relation_name: str = DEFAULT_RELATION_NAME,
        metrics_endpoints: Optional[List["_MetricsEndpointDict"]] = None,
        metrics_rules_dir: str = "./src/prometheus_alert_rules",
        logs_rules_dir: str = "./src/loki_alert_rules",
        recurse_rules_dirs: bool = False,
        log_slots: Optional[List[str]] = None,
        dashboard_dirs: Optional[List[str]] = None,
        refresh_events: Optional[List] = None,
        tracing_protocols: Optional[List[str]] = None,
        *,
        scrape_configs: Optional[Union[List[dict], Callable]] = None,
    ):
        """Create a COSAgentProvider instance.

        Args:
            charm: The `CharmBase` instance that is instantiating this object.
            relation_name: The name of the relation to communicate over.
            metrics_endpoints: List of endpoints in the form [{"path": path, "port": port}, ...].
                This argument is a simplified form of the `scrape_configs`.
                The contents of this list will be merged with the contents of `scrape_configs`.
            metrics_rules_dir: Directory where the metrics rules are stored.
            logs_rules_dir: Directory where the logs rules are stored.
            recurse_rules_dirs: Whether to recurse into rule paths.
            log_slots: Snap slots to connect to for scraping logs
                in the form ["snap-name:slot", ...].
            dashboard_dirs: Directory where the dashboards are stored.
            refresh_events: List of events on which to refresh relation data.
            tracing_protocols: List of protocols that the charm will be using for sending traces.
            scrape_configs: List of standard scrape_configs dicts or a callable
                that returns the list in case the configs need to be generated dynamically.
                The contents of this list will be merged with the contents of `metrics_endpoints`.
        """
        super().__init__(charm, relation_name)
        dashboard_dirs = dashboard_dirs or ["./src/grafana_dashboards"]

        self._charm = charm
        self._relation_name = relation_name
        self._metrics_endpoints = metrics_endpoints or []
        self._scrape_configs = scrape_configs or []
        self._metrics_rules = metrics_rules_dir
        self._logs_rules = logs_rules_dir
        self._recursive = recurse_rules_dirs
        self._log_slots = log_slots or []
        self._dashboard_dirs = dashboard_dirs
        self._refresh_events = refresh_events or [self._charm.on.config_changed]
        self._tracing_protocols = tracing_protocols
        self._is_single_endpoint = charm.meta.relations[relation_name].limit == 1

        events = self._charm.on[relation_name]
        self.framework.observe(events.relation_joined, self._on_refresh)
        self.framework.observe(events.relation_changed, self._on_refresh)
        for event in self._refresh_events:
            self.framework.observe(event, self._on_refresh)

    def _on_refresh(self, event):
        """Trigger the class to update relation data."""
        relations = self._charm.model.relations[self._relation_name]

        for relation in relations:
            # Before a principal is related to the grafana-agent subordinate, we'd get
            # ModelError: ERROR cannot read relation settings: unit "zk/2": settings not found
            # Add a guard to make sure it doesn't happen.
            if relation.data and self._charm.unit in relation.data:
                # Subordinate relations can communicate only over unit data.
                try:
                    data = CosAgentProviderUnitData(
                        metrics_alert_rules=self._metrics_alert_rules,
                        log_alert_rules=self._log_alert_rules,
                        dashboards=self._dashboards,
                        metrics_scrape_jobs=self._scrape_jobs,
                        log_slots=self._log_slots,
                        tracing_protocols=self._tracing_protocols,
                    )
                    relation.data[self._charm.unit][data.KEY] = data.json()
                except (
                    pydantic.ValidationError,
                    json.decoder.JSONDecodeError,
                ) as e:
                    logger.error("Invalid relation data provided: %s", e)

    @property
    def _scrape_jobs(self) -> List[Dict]:
        """Return a prometheus_scrape-like data structure for jobs.

        https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config
        """
        if callable(self._scrape_configs):
            scrape_configs = self._scrape_configs()
        else:
            # Create a copy of the user scrape_configs, since we will mutate this object
            scrape_configs = self._scrape_configs.copy()

        # Convert "metrics_endpoints" to standard scrape_configs, and add them in
        for endpoint in self._metrics_endpoints:
            scrape_configs.append(
                {
                    "metrics_path": endpoint["path"],
                    "static_configs": [{"targets": [f"localhost:{endpoint['port']}"]}],
                }
            )

        scrape_configs = scrape_configs or []

        # Augment job name to include the app name and a unique id (index)
        for idx, scrape_config in enumerate(scrape_configs):
            scrape_config["job_name"] = "_".join(
                [self._charm.app.name, str(idx), scrape_config.get("job_name", "default")]
            )

        return scrape_configs

    @property
    def _metrics_alert_rules(self) -> Dict:
        """Use (for now) the prometheus_scrape AlertRules to initialize this."""
        alert_rules = AlertRules(
            query_type="promql", topology=JujuTopology.from_charm(self._charm)
        )
        alert_rules.add_path(self._metrics_rules, recursive=self._recursive)
        alert_rules.add(
            generic_alert_groups.application_rules,
            group_name_prefix=JujuTopology.from_charm(self._charm).identifier,
        )
        return alert_rules.as_dict()

    @property
    def _log_alert_rules(self) -> Dict:
        """Use (for now) the loki_push_api AlertRules to initialize this."""
        alert_rules = AlertRules(query_type="logql", topology=JujuTopology.from_charm(self._charm))
        alert_rules.add_path(self._logs_rules, recursive=self._recursive)
        return alert_rules.as_dict()

    @property
    def _dashboards(self) -> List[str]:
        dashboards: List[str] = []
        for d in self._dashboard_dirs:
            for path in Path(d).glob("*"):
                with open(path, "rt") as fp:
                    dashboard = json.load(fp)
                rel_path = str(
                    path.relative_to(self._charm.charm_dir) if path.is_absolute() else path
                )
                # COSAgentProvider is somewhat analogous to GrafanaDashboardProvider. We need to overwrite the uid here
                # because there is currently no other way to communicate the dashboard path separately.
                # https://github.com/canonical/grafana-k8s-operator/pull/363
                dashboard["uid"] = DashboardPath40UID.generate(self._charm.meta.name, rel_path)

                # Add tags
                tags: List[str] = dashboard.get("tags", [])
                if not any(tag.startswith("charm: ") for tag in tags):
                    tags.append(f"charm: {self._charm.meta.name}")
                dashboard["tags"] = tags

                dashboards.append(LZMABase64.compress(json.dumps(dashboard)))
        return dashboards

    @property
    def relations(self) -> List[Relation]:
        """The tracing relations associated with this endpoint."""
        return self._charm.model.relations[self._relation_name]

    @property
    def _relation(self) -> Optional[Relation]:
        """If this wraps a single endpoint, the relation bound to it, if any."""
        if not self._is_single_endpoint:
            objname = type(self).__name__
            raise AmbiguousRelationUsageError(
                f"This {objname} wraps a {self._relation_name} endpoint that has "
                "limit != 1. We can't determine what relation, of the possibly many, you are "
                f"referring to. Please pass a relation instance while calling {objname}, "
                "or set limit=1 in the charm metadata."
            )
        relations = self.relations
        return relations[0] if relations else None

    def is_ready(self, relation: Optional[Relation] = None):
        """Is this endpoint ready?"""
        relation = relation or self._relation
        if not relation:
            logger.debug(f"no relation on {self._relation_name!r}: tracing not ready")
            return False
        if relation.data is None:
            logger.error(f"relation data is None for {relation}")
            return False
        if not relation.app:
            logger.error(f"{relation} event received but there is no relation.app")
            return False
        try:
            unit = next(iter(relation.units), None)
            if not unit:
                return False
            databag = dict(relation.data[unit])
            CosAgentRequirerUnitData.load(databag)

        except (json.JSONDecodeError, pydantic.ValidationError, DataValidationError):
            logger.info(f"failed validating relation data for {relation}")
            return False
        return True

    def get_all_endpoints(
        self, relation: Optional[Relation] = None
    ) -> Optional[CosAgentRequirerUnitData]:
        """Unmarshalled relation data."""
        relation = relation or self._relation
        if not relation or not self.is_ready(relation):
            return None
        unit = next(iter(relation.units), None)
        if not unit:
            return None
        return CosAgentRequirerUnitData.load(relation.data[unit])  # type: ignore

    def _get_tracing_endpoint(
        self, relation: Optional[Relation], protocol: ReceiverProtocol
    ) -> str:
        """Return a tracing endpoint URL if it is available or raise a ProtocolNotFoundError."""
        unit_data = self.get_all_endpoints(relation)
        if not unit_data:
            # we didn't find the protocol because the remote end didn't publish any data yet
            # it might also mean that grafana-agent doesn't have a relation to the tracing backend
            raise ProtocolNotFoundError(protocol)
        receivers: List[Receiver] = [i for i in unit_data.receivers if i.protocol.name == protocol]
        if not receivers:
            # we didn't find the protocol because grafana-agent didn't return us the protocol that we requested
            # the caller might want to verify that we did indeed request this protocol
            raise ProtocolNotFoundError(protocol)
        if len(receivers) > 1:
            logger.warning(
                f"too many receivers with protocol={protocol!r}; using first one. Found: {receivers}"
            )

        receiver = receivers[0]
        if not receiver.url:
            # grafana-agent isn't connected to the tracing backend yet
            raise ProtocolNotFoundError(protocol)
        return receiver.url

    def get_tracing_endpoint(
        self, protocol: ReceiverProtocol, relation: Optional[Relation] = None
    ) -> str:
        """Receiver endpoint for the given protocol.

        It could happen that this function gets called before the provider publishes the endpoints.
        In such a scenario, if a non-leader unit calls this function, a permission denied exception will be raised due to
        restricted access. To prevent this, this function needs to be guarded by the `is_ready` check.

        Raises:
        ProtocolNotRequestedError:
            If the charm unit is the leader unit and attempts to obtain an endpoint for a protocol it did not request.
        ProtocolNotFoundError:
            If the charm attempts to obtain an endpoint when grafana-agent isn't related to a tracing backend.
        """
        try:
            return self._get_tracing_endpoint(relation or self._relation, protocol=protocol)
        except ProtocolNotFoundError:
            # let's see if we didn't find it because we didn't request the endpoint
            requested_protocols = set()
            relations = [relation] if relation else self.relations
            for relation in relations:
                try:
                    databag = CosAgentProviderUnitData.load(relation.data[self._charm.unit])
                except DataValidationError:
                    continue

                if databag.tracing_protocols:
                    requested_protocols.update(databag.tracing_protocols)

            if protocol not in requested_protocols:
                raise ProtocolNotRequestedError(protocol, relation)

            raise


class COSAgentDataChanged(EventBase):
    """Event emitted by `COSAgentRequirer` when relation data changes."""


class COSAgentValidationError(EventBase):
    """Event emitted by `COSAgentRequirer` when there is an error in the relation data."""

    def __init__(self, handle, message: str = ""):
        super().__init__(handle)
        self.message = message

    def snapshot(self) -> Dict:
        """Save COSAgentValidationError source information."""
        return {"message": self.message}

    def restore(self, snapshot):
        """Restore COSAgentValidationError source information."""
        self.message = snapshot["message"]


class COSAgentRequirerEvents(ObjectEvents):
    """`COSAgentRequirer` events."""

    data_changed = EventSource(COSAgentDataChanged)
    validation_error = EventSource(COSAgentValidationError)


class COSAgentRequirer(Object):
    """Integration endpoint wrapper for the Requirer side of the cos_agent interface."""

    on = COSAgentRequirerEvents()  # pyright: ignore

    def __init__(
        self,
        charm: CharmType,
        *,
        relation_name: str = DEFAULT_RELATION_NAME,
        peer_relation_name: str = DEFAULT_PEER_RELATION_NAME,
        refresh_events: Optional[List[str]] = None,
        is_tracing_ready: Optional[Callable] = None,
    ):
        """Create a COSAgentRequirer instance.

        Args:
            charm: The `CharmBase` instance that is instantiating this object.
            relation_name: The name of the relation to communicate over.
            peer_relation_name: The name of the peer relation to communicate over.
            refresh_events: List of events on which to refresh relation data.
            is_tracing_ready: Custom function to evaluate whether the trace receiver url should be sent.
        """
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name
        self._peer_relation_name = peer_relation_name
        self._refresh_events = refresh_events or [self._charm.on.config_changed]
        self._is_tracing_ready = is_tracing_ready

        events = self._charm.on[relation_name]
        self.framework.observe(
            events.relation_joined, self._on_relation_data_changed
        )  # TODO: do we need this?
        self.framework.observe(events.relation_changed, self._on_relation_data_changed)
        self.framework.observe(events.relation_departed, self._on_relation_departed)

        for event in self._refresh_events:
            self.framework.observe(event, self.trigger_refresh)  # pyright: ignore

        # Peer relation events
        # A peer relation is needed as it is the only mechanism for exchanging data across
        # subordinate units.
        # self.framework.observe(
        #     self.on[self._peer_relation_name].relation_joined, self._on_peer_relation_joined
        # )
        peer_events = self._charm.on[peer_relation_name]
        self.framework.observe(peer_events.relation_changed, self._on_peer_relation_changed)

    @property
    def peer_relation(self) -> Optional["Relation"]:
        """Helper function for obtaining the peer relation object.

        Returns: peer relation object
        (NOTE: would return None if called too early, e.g. during install).
        """
        return self.model.get_relation(self._peer_relation_name)

    def _on_peer_relation_changed(self, _):
        # Peer data is used for forwarding data from principal units to the grafana agent
        # subordinate leader, for updating the app data of the outgoing o11y relations.
        if self._charm.unit.is_leader():
            self.on.data_changed.emit()  # pyright: ignore

    def _on_relation_departed(self, event):
        """Remove provider's (principal's) alert rules and dashboards from peer data when the cos-agent relation to the principal is removed."""
        if not self.peer_relation:
            event.defer()
            return
        # empty the departing unit's alert rules and dashboards from peer data
        data = CosAgentPeersUnitData(
            unit_name=event.unit.name,
            relation_id=str(event.relation.id),
            relation_name=event.relation.name,
            metrics_alert_rules={},
            log_alert_rules={},
            dashboards=[],
        )
        self.peer_relation.data[self._charm.unit][
            f"{CosAgentPeersUnitData.KEY}-{event.unit.name}"
        ] = data.json()

        self.on.data_changed.emit()  # pyright: ignore

    def _on_relation_data_changed(self, event: RelationChangedEvent):
        # Peer data is the only means of communication between subordinate units.
        if not self.peer_relation:
            event.defer()
            return

        cos_agent_relation = event.relation
        if not event.unit or not cos_agent_relation.data.get(event.unit):
            return
        principal_unit = event.unit

        # Coherence check
        units = cos_agent_relation.units
        if len(units) > 1:
            # should never happen
            raise ValueError(
                f"unexpected error: subordinate relation {cos_agent_relation} "
                f"should have exactly one unit"
            )

        if not (raw := cos_agent_relation.data[principal_unit].get(CosAgentProviderUnitData.KEY)):
            return

        if not (provider_data := self._validated_provider_data(raw)):
            return

        # write enabled receivers to cos-agent relation
        try:
            self.update_tracing_receivers()
        except ModelError:
            raise

        # Copy data from the cos_agent relation to the peer relation, so the leader could
        # follow up.
        # Save the originating unit name, so it could be used for topology later on by the leader.
        data = CosAgentPeersUnitData(  # peer relation databag model
            unit_name=event.unit.name,
            relation_id=str(event.relation.id),
            relation_name=event.relation.name,
            metrics_alert_rules=provider_data.metrics_alert_rules,
            log_alert_rules=provider_data.log_alert_rules,
            dashboards=provider_data.dashboards,
        )
        self.peer_relation.data[self._charm.unit][
            f"{CosAgentPeersUnitData.KEY}-{event.unit.name}"
        ] = data.json()

        # We can't easily tell if the data that was changed is limited to only the data
        # that goes into peer relation (in which case, if this is not a leader unit, we wouldn't
        # need to emit `on.data_changed`), so we're emitting `on.data_changed` either way.
        self.on.data_changed.emit()  # pyright: ignore

    def update_tracing_receivers(self):
        """Updates the list of exposed tracing receivers in all relations."""
        tracing_ready = (
            self._is_tracing_ready if self._is_tracing_ready else self._charm.tracing.is_ready  # type: ignore
        )
        try:
            for relation in self._charm.model.relations[self._relation_name]:
                CosAgentRequirerUnitData(
                    receivers=[
                        Receiver(
                            # if tracing isn't ready, we don't want the wrong receiver URLs present in the databag.
                            # however, because of the backwards compatibility requirements, we need to still provide
                            # the protocols list so that the charm with older cos_agent version doesn't error its hooks.
                            # before this change was added, the charm with old cos_agent version threw exceptions with
                            # connections to grafana-agent timing out. After the change, the charm will fail validating
                            # databag contents (as it expects a string in URL) but that won't cause any errors as
                            # tracing endpoints are the only content in the grafana-agent's side of the databag.
                            url=f"{self._get_tracing_receiver_url(protocol)}"
                            if tracing_ready()
                            else None,
                            protocol=ProtocolType(
                                name=protocol,
                                type=receiver_protocol_to_transport_protocol[protocol],
                            ),
                        )
                        for protocol in self.requested_tracing_protocols()
                    ],
                ).dump(relation.data[self._charm.unit])

        except ModelError as e:
            # args are bytes
            msg = e.args[0]
            if isinstance(msg, bytes):
                if msg.startswith(
                    b"ERROR cannot read relation application settings: permission denied"
                ):
                    logger.error(
                        f"encountered error {e} while attempting to update_relation_data."
                        f"The relation must be gone."
                    )
                    return
            raise

    def _validated_provider_data(self, raw) -> Optional[CosAgentProviderUnitData]:
        try:
            return CosAgentProviderUnitData(**json.loads(raw))
        except (pydantic.ValidationError, json.decoder.JSONDecodeError) as e:
            self.on.validation_error.emit(message=str(e))  # pyright: ignore
            return None

    def trigger_refresh(self, _):
        """Trigger a refresh of relation data."""
        # FIXME: Figure out what we should do here
        self.on.data_changed.emit()  # pyright: ignore

    def _get_requested_protocols(self, relation: Relation):
        # Coherence check
        units = relation.units
        if len(units) > 1:
            # should never happen
            raise ValueError(
                f"unexpected error: subordinate relation {relation} should have exactly one unit"
            )

        unit = next(iter(units), None)

        if not unit:
            return None

        if not (raw := relation.data[unit].get(CosAgentProviderUnitData.KEY)):
            return None

        if not (provider_data := self._validated_provider_data(raw)):
            return None

        return provider_data.tracing_protocols

    def requested_tracing_protocols(self):
        """All receiver protocols that have been requested by our related apps."""
        requested_protocols = set()
        for relation in self._charm.model.relations[self._relation_name]:
            try:
                protocols = self._get_requested_protocols(relation)
            except NotReadyError:
                continue
            if protocols:
                requested_protocols.update(protocols)
        return requested_protocols

    def _get_tracing_receiver_url(self, protocol: str):
        scheme = "http"
        try:
            if self._charm.cert.enabled:  # type: ignore
                scheme = "https"
        # not only Grafana Agent can implement cos_agent. If the charm doesn't have the `cert` attribute
        # using our cert_handler, it won't have the `enabled` parameter. In this case, we pass and assume http.
        except AttributeError:
            pass
        # the assumption is that a subordinate charm will always be accessible to its principal charm under its fqdn
        if receiver_protocol_to_transport_protocol[protocol] == TransportProtocolType.grpc:
            return f"{socket.getfqdn()}:{_tracing_receivers_ports[protocol]}"
        return f"{scheme}://{socket.getfqdn()}:{_tracing_receivers_ports[protocol]}"

    @property
    def _remote_data(self) -> List[Tuple[CosAgentProviderUnitData, JujuTopology]]:
        """Return a list of remote data from each of the related units.

        Assumes that the relation is of type subordinate.
        Relies on the fact that, for subordinate relations, the only remote unit visible to
        *this unit* is the principal unit that this unit is attached to.
        """
        all_data = []

        for relation in self._charm.model.relations[self._relation_name]:
            if not relation.units:
                continue
            unit = next(iter(relation.units))
            if not (raw := relation.data[unit].get(CosAgentProviderUnitData.KEY)):
                continue
            if not (provider_data := self._validated_provider_data(raw)):
                continue

            topology = JujuTopology(
                model=self._charm.model.name,
                model_uuid=self._charm.model.uuid,
                application=unit.app.name,
                unit=unit.name,
            )

            all_data.append((provider_data, topology))

        return all_data

    def _gather_peer_data(self) -> List[CosAgentPeersUnitData]:
        """Collect data from the peers.

        Returns a trimmed-down list of CosAgentPeersUnitData.
        """
        relation = self.peer_relation

        # Ensure that whatever context we're running this in, we take the necessary precautions:
        if not relation or not relation.data or not relation.app:
            return []

        # Iterate over all peer unit data and only collect every principal once.
        peer_data: List[CosAgentPeersUnitData] = []
        app_names: Set[str] = set()

        for unit in chain((self._charm.unit,), relation.units):
            if not relation.data.get(unit):
                continue

            for unit_name in relation.data.get(unit):  # pyright: ignore
                if not unit_name.startswith(CosAgentPeersUnitData.KEY):
                    continue
                raw = relation.data[unit].get(unit_name)
                if raw is None:
                    continue
                data = CosAgentPeersUnitData(**json.loads(raw))
                # Have we already seen this principal app?
                if (app_name := data.app_name) in app_names:
                    continue
                peer_data.append(data)
                app_names.add(app_name)

        return peer_data

    @property
    def metrics_alerts(self) -> Dict[str, Any]:
        """Fetch metrics alerts."""
        alert_rules = {}

        seen_apps: List[str] = []
        for data in self._gather_peer_data():
            if rules := data.metrics_alert_rules:
                app_name = data.app_name
                if app_name in seen_apps:
                    continue  # dedup!
                seen_apps.append(app_name)
                # This is only used for naming the file, so be as specific as we can be
                identifier = JujuTopology(
                    model=self._charm.model.name,
                    model_uuid=self._charm.model.uuid,
                    application=app_name,
                    # For the topology unit, we could use `data.principal_unit_name`, but that unit
                    # name may not be very stable: `_gather_peer_data` de-duplicates by app name so
                    # the exact unit name that turns up first in the iterator may vary from time to
                    # time. So using the grafana-agent unit name instead.
                    unit=self._charm.unit.name,
                ).identifier

                alert_rules[identifier] = rules

        return alert_rules

    @property
    def metrics_jobs(self) -> List[Dict]:
        """Parse the relation data contents and extract the metrics jobs."""
        scrape_jobs = []
        for data, topology in self._remote_data:
            for job in data.metrics_scrape_jobs:
                # In #220, relation schema changed from a simplified dict to the standard
                # `scrape_configs`.
                # This is to ensure backwards compatibility with Providers older than v0.5.
                if "path" in job and "port" in job and "job_name" in job:
                    job = {
                        "job_name": job["job_name"],
                        "metrics_path": job["path"],
                        "static_configs": [{"targets": [f"localhost:{job['port']}"]}],
                        # We include insecure_skip_verify because we are always scraping localhost.
                        # Even if we have the certs for the scrape targets, we'd rather specify the scrape
                        # jobs with localhost rather than the SAN DNS the cert was issued for.
                        "tls_config": {"insecure_skip_verify": True},
                    }

                # Apply labels to the scrape jobs
                for static_config in job.get("static_configs", []):
                    topo_as_dict = topology.as_dict(excluded_keys=["charm_name"])
                    static_config["labels"] = {
                        # Be sure to keep labels from static_config
                        **static_config.get("labels", {}),
                        # TODO: We should add a new method in juju_topology.py
                        # that like `as_dict` method, returns the keys with juju_ prefix
                        # https://github.com/canonical/cos-lib/issues/18
                        **{
                            "juju_{}".format(key): value
                            for key, value in topo_as_dict.items()
                            if value
                        },
                    }

                scrape_jobs.append(job)

        return scrape_jobs

    @property
    def snap_log_endpoints(self) -> List[SnapEndpoint]:
        """Fetch logging endpoints exposed by related snaps."""
        endpoints = []
        endpoints_with_topology = self.snap_log_endpoints_with_topology
        for endpoint, _ in endpoints_with_topology:
            endpoints.append(endpoint)

        return endpoints

    @property
    def snap_log_endpoints_with_topology(self) -> List[Tuple[SnapEndpoint, JujuTopology]]:
        """Fetch logging endpoints and charm topology for each related snap."""
        plugs = []
        for data, topology in self._remote_data:
            targets = data.log_slots
            if targets:
                for target in targets:
                    if target in plugs:
                        logger.warning(
                            f"plug {target} already listed. "
                            "The same snap is being passed from multiple "
                            "endpoints; this should not happen."
                        )
                    else:
                        plugs.append((target, topology))

        endpoints = []
        for plug, topology in plugs:
            if ":" not in plug:
                logger.error(f"invalid plug definition received: {plug}. Ignoring...")
            else:
                endpoint = SnapEndpoint(*plug.split(":"))
                endpoints.append((endpoint, topology))

        return endpoints

    @property
    def logs_alerts(self) -> Dict[str, Any]:
        """Fetch log alerts."""
        alert_rules = {}
        seen_apps: List[str] = []

        for data in self._gather_peer_data():
            if rules := data.log_alert_rules:
                # This is only used for naming the file, so be as specific as we can be
                app_name = data.app_name
                if app_name in seen_apps:
                    continue  # dedup!
                seen_apps.append(app_name)

                identifier = JujuTopology(
                    model=self._charm.model.name,
                    model_uuid=self._charm.model.uuid,
                    application=app_name,
                    # For the topology unit, we could use `data.unit_name`, but that unit
                    # name may not be very stable: `_gather_peer_data` de-duplicates by app name so
                    # the exact unit name that turns up first in the iterator may vary from time to
                    # time. So using the grafana-agent unit name instead.
                    unit=self._charm.unit.name,
                ).identifier

                alert_rules[identifier] = rules

        return alert_rules

    @property
    def dashboards(self) -> List[Dict[str, str]]:
        """Fetch dashboards as encoded content.

        Dashboards are assumed not to vary across units of the same primary.
        """
        dashboards: List[Dict[str, Any]] = []

        seen_apps: List[str] = []
        for data in self._gather_peer_data():
            app_name = data.app_name
            if app_name in seen_apps:
                continue  # dedup!
            seen_apps.append(app_name)

            for encoded_dashboard in data.dashboards or ():
                content = json.loads(LZMABase64.decompress(encoded_dashboard))

                title = content.get("title", "no_title")

                dashboards.append(
                    {
                        "relation_id": data.relation_id,
                        # We have the remote charm name - use it for the identifier
                        "charm": f"{data.relation_name}-{app_name}",
                        "content": content,
                        "title": title,
                    }
                )

        return dashboards


def charm_tracing_config(
    endpoint_requirer: COSAgentProvider, cert_path: Optional[Union[Path, str]]
) -> Tuple[Optional[str], Optional[str]]:
    """Utility function to determine the charm_tracing config you will likely want.

    If no endpoint is provided:
     disable charm tracing.
    If https endpoint is provided but cert_path is not found on disk:
     disable charm tracing.
    If https endpoint is provided and cert_path is None:
     raise TracingError
    Else:
     proceed with charm tracing (with or without tls, as appropriate)

    Usage:
    >>> from lib.charms.tempo_coordinator_k8s.v0.charm_tracing import trace_charm
    >>> from lib.charms.tempo_coordinator_k8s.v0.tracing import charm_tracing_config
    >>> @trace_charm(tracing_endpoint="my_endpoint", cert_path="cert_path")
    >>> class MyCharm(...):
    >>>     _cert_path = "/path/to/cert/on/charm/container.crt"
    >>>     def __init__(self, ...):
    >>>         self.tracing = TracingEndpointRequirer(...)
    >>>         self.my_endpoint, self.cert_path = charm_tracing_config(
    ...             self.tracing, self._cert_path)
    """
    if not endpoint_requirer.is_ready():
        return None, None

    try:
        endpoint = endpoint_requirer.get_tracing_endpoint("otlp_http")
    except ProtocolNotFoundError:
        logger.warn(
            "Endpoint for tracing wasn't provided as tracing backend isn't ready yet. If grafana-agent isn't connected to a tracing backend, integrate it. Otherwise this issue should resolve itself in a few events."
        )
        return None, None

    if not endpoint:
        return None, None

    is_https = endpoint.startswith("https://")

    if is_https:
        if cert_path is None:
            raise TracingError("Cannot send traces to an https endpoint without a certificate.")
        if not Path(cert_path).exists():
            # if endpoint is https BUT we don't have a server_cert yet:
            # disable charm tracing until we do to prevent tls errors
            return None, None
        return endpoint, str(cert_path)
    return endpoint, None
