# Copyright 2024 Canonical
# See LICENSE file for licensing details.

import logging
import subprocess

logger = logging.getLogger(__name__)


def run_with_logged_errors(cmd: list) -> int:
    """Run a command, log output if errors, return exit code"""
    proc = subprocess.run(
        cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, text=True
    )
    if proc.returncode:
        logger.error(proc.stdout)
    return proc.returncode
