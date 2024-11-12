from testflinger_agent.handlers import LogUpdateHandler
from testflinger_agent.masking import Masker
from testflinger_agent.runner import CommandRunner, MaskingCommandRunner


def test_runner(tmp_path):
    """Check that runner output is as expected"""
    logfile = tmp_path / "testlog"
    log_handler = LogUpdateHandler(logfile)
    runner = CommandRunner(tmp_path, env={})
    runner.register_output_handler(log_handler)
    exit_code, _, _ = runner.run("echo -n Message")
    with open(logfile) as log:
        log_data = log.read()
    assert exit_code == 0
    assert log_data == "Message"


def test_runner_environment(tmp_path):
    """Check injection of environment variables"""
    logfile = tmp_path / "testlog"
    log_handler = LogUpdateHandler(logfile)
    runner = CommandRunner(tmp_path, env={"MESSAGE": "Message"})
    runner.register_output_handler(log_handler)
    exit_code, _, _ = runner.run("echo -n $MESSAGE")
    with open(logfile) as log:
        log_data = log.read()
    assert exit_code == 0
    assert log_data == "Message"


def test_masking_runner(tmp_path):
    """Check masking"""
    logfile = tmp_path / "testlog"
    log_handler = LogUpdateHandler(logfile)
    hash_length = 24
    non_sensitive = "Message: "
    sensitive = "Sensitive"
    masker = Masker([sensitive], hash_length=hash_length)
    runner = MaskingCommandRunner(tmp_path, env={}, masker=masker)
    runner.register_output_handler(log_handler)
    exit_code, _, _ = runner.run(f"echo -n {non_sensitive}{sensitive}")
    with open(logfile) as log:
        log_data = log.read()
    assert exit_code == 0
    assert log_data.startswith("Message: ")
    assert "Sensitive" not in log_data
    assert len(log_data) == len(non_sensitive) + hash_length + 4


def test_masking_runner_environment(tmp_path):
    """Check masking of sensitive environment variables"""
    logfile = tmp_path / "testlog"
    log_handler = LogUpdateHandler(logfile)
    hash_length = 24
    non_sensitive = "Message: "
    sensitive = {"SECRET1": "secret", "SECRET2": "another_secret"}
    masker = Masker(list(sensitive.values()), hash_length=hash_length)
    runner = MaskingCommandRunner(tmp_path, env=sensitive, masker=masker)
    runner.register_output_handler(log_handler)
    exit_code, _, _ = runner.run(
        f"echo -n {non_sensitive}{sensitive['SECRET1']}{sensitive['SECRET2']}"
    )
    with open(logfile) as log:
        log_data = log.read()
    assert exit_code == 0
    assert log_data.startswith("Message: ")
    assert "secret" not in log_data
    assert "another_secret" not in log_data
    assert len(log_data) == len(non_sensitive) + 2 * (hash_length + 4)
