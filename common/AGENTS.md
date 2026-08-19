# Preface

Testflinger Common is a small shared library of enums and utilities (e.g. job/phase states, duration parsing) used to avoid duplication across other components.
Read the top-level `.kb/agents.md` file before continuing below.


# Important

- The CLI cannot depend on this library because of Snap confinement. When changing a type mirrored in `src/testflinger_common/enums.py`, update the corresponding local copy in `../cli/testflinger_cli/enums.py` as part of the same change.


# Directory

- `src/testflinger_common/` - Library source (enums, duration parsing).
- `tests/` - Unit tests.
- `justfile` - Task runner (format/lint/test/check).
