# Copyright (C) 2022 Canonical
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

"""
Unit tests for testflinger-cli
"""

import json
import sys
import uuid
import pytest

import testflinger_cli


URL = "https://testflinger.canonical.com"


def test_status(capsys, requests_mock):
    """ Status should report job_state data """
    jobid = str(uuid.uuid1())
    fake_return = {"job_state": "complete"}
    requests_mock.get(URL+"/v1/result/"+jobid, json=fake_return)
    sys.argv = ['', 'status', jobid]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.status()
    std = capsys.readouterr()
    assert std.out == "complete\n"


def test_cancel(requests_mock):
    """ Cancel should fail if job is already complete """
    jobid = str(uuid.uuid1())
    fake_return = {"job_state": "complete"}
    requests_mock.get(URL+"/v1/result/"+jobid, json=fake_return)
    requests_mock.post(URL+"/v1/result/"+jobid)
    sys.argv = ['', 'cancel', jobid]
    tfcli = testflinger_cli.TestflingerCli()
    with pytest.raises(SystemExit) as err:
        tfcli.cancel()
    assert "already in complete state and cannot" in err.value.args[0]


def test_submit(capsys, tmp_path, requests_mock):
    """ Make sure jobid is read back from submitted job """
    jobid = str(uuid.uuid1())
    fake_data = {
        "queue": "fake",
        "provision_data": {
            "distro": "fake"
        }
    }
    testfile = tmp_path / "test.json"
    testfile.write_text(json.dumps(fake_data))
    fake_return = {"job_id": jobid}
    requests_mock.post(URL+"/v1/job", json=fake_return)
    sys.argv = ['', 'submit', str(testfile)]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.submit()
    std = capsys.readouterr()
    assert jobid in std.out


def test_show(capsys, requests_mock):
    """ Exercise show command """
    jobid = str(uuid.uuid1())
    fake_return = {"job_state": "complete"}
    requests_mock.get(URL+"/v1/job/"+jobid, json=fake_return)
    sys.argv = ['', 'show', jobid]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.show()
    std = capsys.readouterr()
    assert "complete" in std.out


def test_results(capsys, requests_mock):
    """ results should report job_state data """
    jobid = str(uuid.uuid1())
    fake_return = {"job_state": "complete"}
    requests_mock.get(URL+"/v1/result/"+jobid, json=fake_return)
    sys.argv = ['', 'results', jobid]
    tfcli = testflinger_cli.TestflingerCli()
    tfcli.results()
    std = capsys.readouterr()
    assert "complete" in std.out
