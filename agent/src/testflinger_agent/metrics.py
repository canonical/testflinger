# Copyright (C) 2025 Canonical
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import logging
from abc import ABC, abstractmethod

from prometheus_client import (
    Counter,
    disable_created_metrics,
    start_http_server,
)

logger = logging.getLogger(__name__)


class MetricsHandler(ABC):
    """Abstract class to handle agent metrics to a generic backend."""

    @abstractmethod
    def report_new_job(self):
        """Report a new job to the metrics backend."""
        raise NotImplementedError

    @abstractmethod
    def report_job_failure(self):
        """Report a job failure to the metrics backend."""
        raise NotImplementedError


class PrometheusHandler(MetricsHandler):
    """Handler to store metrics for a Prometheus Metric Endpoint."""

    def __init__(self, port: int):
        disable_created_metrics()
        self.total_jobs = Counter(
            "jobs",
            "Total jobs processed since last agent restart",
        )
        self.total_failures = Counter(
            "failures",
            "Total job failures since last agent restart",
            ["test_phase"],
        )
        try:
            start_http_server(port)
        except Exception:
            logger.error("Unable to start metrics endpoint")

    def report_new_job(self):
        """Increase total job counter and push to gateway."""
        self.total_jobs.inc()

    def report_job_failure(self, phase: str):
        """Increase total failures counter and push to gateway."""
        self.total_failures.labels(phase).inc()
