# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import re
import socket
from pathlib import Path
from typing import Optional, Tuple

from common import run_with_logged_errors

logger = logging.getLogger(__name__)
SUPERVISOR_CONF_DIR = "/etc/supervisor/conf.d"
TESTFLINGER_AGENT_CMD = "testflinger-agent"
DEFAULT_PORT_RANGE_START = 8000
DEFAULT_PORT_RANGE_END = 10000


def get_supervisor_agents_port_mapping() -> dict[str, int]:
    """Get current agent:port mapping from supervisor config files.

    Returns:
        dict: Mapping of agent names to their configured ports.
             Empty dict if no valid configurations found.
    """
    agent_port_mapping = {}
    supervisor_conf_dir = Path(SUPERVISOR_CONF_DIR)

    if not supervisor_conf_dir.exists():
        logger.debug(
            "Supervisor config directory %s does not exist",
            supervisor_conf_dir,
        )
        return agent_port_mapping

    try:
        for conf_file in supervisor_conf_dir.iterdir():
            if conf_file.suffix == ".conf":
                conf_path = str(conf_file)
                try:
                    agent_name, port = parse_supervisor_config_file(conf_path)
                    if agent_name and port:
                        agent_port_mapping[agent_name] = port
                        logger.debug(
                            "Found configured agent %s on port %s",
                            agent_name,
                            port,
                        )
                except (OSError, IOError) as e:
                    logger.debug(
                        "Failed to read config file %s: %s", conf_path, e
                    )
                    continue
                except ValueError as e:
                    logger.debug(
                        "Failed to parse port number in %s: %s",
                        conf_path,
                        e,
                    )
                    continue
    except (OSError, IOError) as e:
        logger.warning("Failed to read supervisor config files: %s", e)

    return agent_port_mapping


def parse_supervisor_config_file(
    conf_path: str,
) -> Tuple[Optional[str], Optional[int]]:
    """Extract agent name and port from supervisor config file.

    Returns:
        tuple: (agent_name, port) if both found, (None, None) otherwise.
    """
    try:
        agent_name = None
        port = None

        with open(conf_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()

                if line.startswith("[program:"):
                    program_match = re.search(r"\[program:([^\]]+)\]", line)
                    if program_match:
                        agent_name = program_match.group(1)
                elif (
                    line.startswith("command=")
                    and TESTFLINGER_AGENT_CMD in line
                ):
                    port_match = re.search(r"-p (\d+)", line)
                    if port_match:
                        port = int(port_match.group(1))

                if agent_name and port:
                    return agent_name, port
        return None, None

    except (OSError, IOError) as e:
        logger.debug("Failed to read config file '%s': %s", conf_path, e)
        return None, None
    except ValueError as e:
        logger.debug("Failed to parse port number in '%s': %s", conf_path, e)
        return None, None


def find_available_port(
    used_ports: set[int],
    start_port: int = DEFAULT_PORT_RANGE_START,
    max_port: int = DEFAULT_PORT_RANGE_END,
) -> int:
    """Find an available port avoiding used ports."""
    for port in range(start_port, max_port):
        if port in used_ports:
            continue

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"No available ports found in range {start_port}-{max_port}"
    )


def assign_metrics_port(
    agent_name: str,
    configured_agents: dict[str, int],
    used_ports: set[int],
) -> int:
    """Assign a metrics port using supervisor config file discovery."""
    # Check if agent is already configured with a port
    if agent_name in configured_agents:
        current_port = configured_agents[agent_name]
        logger.info(
            "Agent %s keeping existing port %s",
            agent_name,
            current_port,
        )
        return current_port
    # If not configured, find a new port
    try:
        port = find_available_port(used_ports)
        logger.info("Assigned new port %s to agent %s", port, agent_name)
        return port
    except RuntimeError as e:
        logger.error("Failed to find available port for %s: %s", agent_name, e)
        raise


def supervisor_update():
    """
    Once supervisord service files have been written, new agents will be
    automatically started, and missing agents will be removed by running
    `supervisorctl update`. This only applies to supervisor conf files
    that have changed. So any agents for which the conf file has not
    changed will be unaffected.
    """
    run_with_logged_errors(["supervisorctl", "update"])


def restart_agents(self):
    """
    Mark all agents as needing a restart when they are not running a job
    so that they read any updated config files and run the latest
    version of the agent code.
    """
    run_with_logged_errors(["supervisorctl", "signal", "USR1", "all"])
