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
    Histogram,
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
    def report_job_failure(self, phase: str):
        """Report a job failure to the metrics backend.

        :param phase: The phase where the failure occurred
        """
        raise NotImplementedError

    @abstractmethod
    def report_phase_duration(self, phase: str, duration: int):
        """Report the duration of a job phase to the metrics backend.

        :param phase: Phase that reports the duration
        :param duration: The duration of the phase in seconds
        """
        raise NotImplementedError

    @abstractmethod
    def report_recovery_failures(self):
        """Report a recovery failure to the metrics backend."""
        raise NotImplementedError


class PrometheusHandler(MetricsHandler):
    """Handler to store metrics for a Prometheus Metric Endpoint."""

    def __init__(self, port: int, agent_id: str):
        disable_created_metrics()
        self.agent_id = agent_id
        self.total_jobs = Counter(
            "jobs",
            "Total jobs processed since last agent restart",
            ["agent_id"],
        )
        self.total_failures = Counter(
            "failures",
            "Total job failures since last agent restart",
            ["agent_id", "test_phase"],
        )
        # Add custom buckets to handle longer test phases
        self.phase_duration = Histogram(
            "phase_duration_seconds",
            "Duration of each job phase in seconds since last agent restart",
            ["agent_id", "test_phase"],
            buckets=(60, 120, 300, 600, 1800, 3600, 7200, 14400),
        )
        self.recovery_failures = Counter(
            "recovery_failures",
            "Total recovery failures since last agent restart",
            ["agent_id"],
        )
        if port is None:
            return

        try:
            start_http_server(port)
        except Exception as err:
            logger.error("Unable to start metrics endpoint: %s", err)
            raise

    def report_new_job(self):
        """Increase total job counter and push to gateway."""
        self.total_jobs.labels(self.agent_id).inc()

    def report_job_failure(self, phase: str):
        """Increase total failures counter and push to gateway.

        :param phase: The phase where the failure occurred
        """
        self.total_failures.labels(self.agent_id, phase).inc()

    def report_phase_duration(self, phase: str, duration: int):
        """Track phase duration and push to gateway.

        :param phase: Phase that reports the duration
        :param duration: The duration of the phase in seconds
        """
        self.phase_duration.labels(self.agent_id, phase).observe(duration)

    def report_recovery_failures(self):
        """Increase total recovery failures counter and push to gateway."""
        self.recovery_failures.labels(self.agent_id).inc()
