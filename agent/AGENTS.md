# Preface

Testflinger Agent is the per-machine daemon that connects to the Testflinger Server, claims jobs from its queues, and executes them against its attached device.
Read the top-level `.kb/agents.md` file before continuing below.


# Directory

- `src/testflinger_agent/` - Agent daemon source: job polling, config, job lifecycle, and test execution.
- `tests/` - Unit tests.
- `charms/testflinger-agent-host-charm/` - Juju charm for hosting multiple agents on one machine via Supervisor.
- `terraform/` - Infrastructure-as-code for agent deployment.
- `extra/` - Docker and test-environment helpers.
- `justfile` - Task runner (format/lint/test/check).
