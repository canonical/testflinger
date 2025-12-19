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

import uuid
from http import HTTPStatus

import pytest
import requests_mock as rmock
from testflinger_common.enums import TestPhase

import testflinger_agent
from testflinger_agent.client import TestflingerClient as _TestflingerClient
from testflinger_agent.handlers import (
    FileLogHandler,
    OutputLogHandler,
    SerialLogHandler,
)
from testflinger_agent.schema import validate


class TestHandler:
    @pytest.fixture
    def client(self, tmp_path, requests_mock):
        self.config = validate(
            {
                "agent_id": "test01",
                "polling_interval": 2,
                "server_address": "127.0.0.1:8000",
                "job_queues": ["test"],
                "execution_basedir": str(tmp_path),
                "logging_basedir": str(tmp_path),
                "results_basedir": str(tmp_path / "results"),
            }
        )
        testflinger_agent.configure_logging(self.config)
        requests_mock.get(rmock.ANY)
        requests_mock.post(rmock.ANY)
        yield _TestflingerClient(self.config)

    def test_file_log_handler(self, tmp_path):
        filename = tmp_path / "output.log"
        file_log_handler = FileLogHandler(filename)
        file_log_handler("output1")
        with open(filename, "r") as log:
            assert log.read() == "output1"
        file_log_handler("output2")
        with open(filename, "r") as log:
            assert log.read() == "output1output2"

    def test_output_log_handler(self, client, requests_mock):
        job_id = str(uuid.uuid1())
        phase = "phase1"
        output_log_handler = OutputLogHandler(client, job_id, phase)
        output_url = f"http://127.0.0.1:8000/v1/result/{job_id}/log/output"
        requests_mock.post(output_url, status_code=200)
        output_log_handler("output0")
        output_log_handler("output1")
        requests = list(
            filter(
                lambda req: req.url == output_url,
                requests_mock.request_history,
            )
        )
        assert len(requests) == 2
        for i in range(2):
            assert requests[i].json()["fragment_number"] == i
            assert requests[i].json()["phase"] == "phase1"
            assert requests[i].json()["log_data"] == f"output{i}"

    def test_serial_log_handler(self, client, requests_mock):
        job_id = str(uuid.uuid1())
        phase = "phase1"
        serial_log_handler = SerialLogHandler(client, job_id, phase)
        serial_url = f"http://127.0.0.1:8000/v1/result/{job_id}/log/serial"
        requests_mock.post(serial_url, status_code=200)
        serial_log_handler("output0")
        serial_log_handler("output1")
        requests = list(
            filter(
                lambda req: req.url == serial_url,
                requests_mock.request_history,
            )
        )
        assert len(requests) == 2
        for i in range(2):
            assert requests[i].json()["fragment_number"] == i
            assert requests[i].json()["phase"] == "phase1"
            assert requests[i].json()["log_data"] == f"output{i}"

    def test_endpoint_write_from_file(self, client, requests_mock, tmp_path):
        job_id = str(uuid.uuid1())
        phase = "phase1"
        filename = tmp_path / "output.log"
        output = "a" * 2048
        with open(filename, "w") as f:
            f.write(output)
        serial_log_handler = SerialLogHandler(client, job_id, phase)
        serial_url = f"http://127.0.0.1:8000/v1/result/{job_id}/log/serial"
        requests_mock.post(serial_url, status_code=200)
        serial_log_handler.write_from_file(filename)
        requests = list(
            filter(
                lambda req: req.url == serial_url,
                requests_mock.request_history,
            )
        )
        assert len(requests) == 2
        for i in range(2):
            assert requests[i].json()["fragment_number"] == i
            assert requests[i].json()["phase"] == "phase1"
            assert requests[i].json()["log_data"] == "a" * 1024

    def test_endpoint_write_from_file_invalid_utf8(
        self, client, requests_mock, tmp_path
    ):
        """Test binary content is read correctly and sent to endpoint."""
        job_id = str(uuid.uuid1())
        phase = TestPhase.PROVISION
        filename = tmp_path / "provision-serial.log"
        filename.write_bytes(b"Boot OK\n\xff\xfe\nDone")

        serial_log_handler = SerialLogHandler(client, job_id, phase)
        serial_url = f"http://127.0.0.1:8000/v1/result/{job_id}/log/serial"
        requests_mock.post(serial_url, status_code=HTTPStatus.OK)
        serial_log_handler.write_from_file(filename)

        requests = list(
            filter(
                lambda req: req.url == serial_url,
                requests_mock.request_history,
            )
        )

        assert len(requests) == 1
        assert requests[0].json()["fragment_number"] == 0
        assert requests[0].json()["phase"] == phase
        assert requests[0].json()["log_data"] == "Boot OK\n\ufffd\ufffd\nDone"
