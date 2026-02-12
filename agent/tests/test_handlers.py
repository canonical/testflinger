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

from testflinger_agent.handlers import (
    FileLogHandler,
    OutputLogHandler,
    SerialLogHandler,
)


def test_file_log_handler(tmp_path):
    filename = tmp_path / "output.log"
    file_log_handler = FileLogHandler(filename)
    file_log_handler("output1")
    with open(filename, "r") as log:
        assert log.read() == "output1"
    file_log_handler("output2")
    with open(filename, "r") as log:
        assert log.read() == "output1output2"


def test_output_log_handler(client, server_api, requests_mock):
    job_id = str(uuid.uuid1())
    phase = "phase1"
    output_log_handler = OutputLogHandler(client, job_id, phase)
    output_url = f"{server_api}/result/{job_id}/log/output"
    legacy_url = f"{server_api}/result/{job_id}/output"
    requests_mock.post(output_url, status_code=HTTPStatus.OK)
    requests_mock.post(legacy_url, status_code=HTTPStatus.OK)
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


def test_serial_log_handler(client, server_api, requests_mock):
    job_id = str(uuid.uuid1())
    phase = "phase1"
    serial_log_handler = SerialLogHandler(client, job_id, phase)
    serial_url = f"{server_api}/result/{job_id}/log/serial"
    legacy_url = f"{server_api}/result/{job_id}/serial_output"
    requests_mock.post(serial_url, status_code=HTTPStatus.OK)
    requests_mock.post(legacy_url, status_code=HTTPStatus.OK)
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


def test_endpoint_write_from_file(client, server_api, requests_mock, tmp_path):
    job_id = str(uuid.uuid1())
    phase = "phase1"
    filename = tmp_path / "output.log"
    output = "a" * 2048
    with open(filename, "w") as f:
        f.write(output)
    serial_log_handler = SerialLogHandler(client, job_id, phase)
    serial_url = f"{server_api}/result/{job_id}/log/serial"
    legacy_url = f"{server_api}/result/{job_id}/serial_output"
    requests_mock.post(serial_url, status_code=HTTPStatus.OK)
    requests_mock.post(legacy_url, status_code=HTTPStatus.OK)
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
