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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from testflinger_agent.handlers import FileLogHandler
from testflinger_agent.masking import Masker
from testflinger_agent.runner import CommandRunner, MaskingCommandRunner


def run(runner, command, tmp_path):
    logfile = tmp_path / "testlog"
    log_handler = FileLogHandler(logfile)
    runner.register_output_handler(log_handler)
    exit_code, _, _ = runner.run(command)
    with open(logfile) as log:
        log_data = log.read()
    return exit_code, log_data


def test_runner(tmp_path):
    """Check that runner output is as expected."""
    runner = CommandRunner(tmp_path, env={})
    exit_code, log_data = run(runner, "echo -n Message", tmp_path)
    print(log_data)
    assert exit_code == 0
    assert log_data == "Message"


def test_runner_environment(tmp_path):
    """Check injection of environment variables."""
    runner = CommandRunner(tmp_path, env={"MESSAGE": "Message"})
    exit_code, log_data = run(runner, "echo -n $MESSAGE", tmp_path)
    print(log_data)
    assert exit_code == 0
    assert log_data == "Message"


def test_masking_runner(tmp_path):
    """Check masking."""
    hash_length = 24
    non_sensitive = "Message:"
    sensitive = "Sensitive"
    masker = Masker([r"\bSen.*ve\b"], hash_length=hash_length)
    runner = MaskingCommandRunner(tmp_path, env={}, masker=masker)
    exit_code, log_data = run(
        runner, f"echo -n {non_sensitive} {sensitive}", tmp_path
    )
    print(log_data)
    assert exit_code == 0
    assert log_data.startswith(non_sensitive)
    assert sensitive not in log_data
    assert len(log_data) == len(non_sensitive) + 1 + hash_length + 4


def test_masking_runner_environment(tmp_path):
    """Check masking of sensitive environment variables."""
    hash_length = 24
    non_sensitive = "Message:"
    variables = {"ENV_1": "secret", "ENV_2": "another_secret"}
    masker = Masker(patterns=list(variables.values()), hash_length=hash_length)
    runner = MaskingCommandRunner(tmp_path, env=variables, masker=masker)
    exit_code, log_data = run(
        runner,
        f"echo -n {non_sensitive} {variables['ENV_1']} {variables['ENV_2']}",
        tmp_path,
    )
    print(log_data)
    assert exit_code == 0
    assert log_data.startswith("Message: ")
    for value in variables.values():
        assert value not in log_data
    assert len(log_data) == len(non_sensitive) + 2 + 2 * (hash_length + 4)
