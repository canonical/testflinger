# Preface

Testflinger CLI is the user-facing command-line client for submitting jobs to a Testflinger server, polling status, and retrieving results. It is packaged and distributed as a Snap.
Read the top-level `.kb/agents.md` file before continuing below.


# Important

- Do not add a dependency on `testflinger-common`: Snap confinement requires the CLI to maintain local copies of shared types. When changing a type mirrored in `testflinger_cli/enums.py`, update the corresponding type in `../common/` as part of the same change.


# Directory

- `testflinger_cli/` - CLI source: client, admin commands, auth, config, autocomplete, status line.
- `tests/` - Unit tests.
- `snapcraft.yaml` - Snap packaging definition.
- `testflinger-completion` - Shell completion script.
- `HACKING.md` - Developer setup notes.
- `justfile` - Task runner (format/lint/test/check).
