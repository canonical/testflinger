# Preface

Testflinger Device Connectors provision, run tests on, and recover target devices on behalf of an agent, abstracting device-specific logic behind a common interface.
Read the top-level `.kb/agents.md` file before continuing below.


# Directory

- `src/testflinger_device_connectors/` - Connector source: CLI entry point (`cmd.py`), `devices/` (per-device implementations), `fw_devices/` (firmware handling), `data/` (per-device provisioning data, e.g. cloud-init templates and scripts).
- `tests/` - Unit tests.
- `HACKING.md` - Developer setup notes.
- `justfile` - Task runner (format/lint/test/check).
