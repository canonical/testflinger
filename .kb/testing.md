# Preface

Explains the cross-component developer workflow for building, linting, and testing the Python components (`agent/`, `cli/`, `common/`, `device-connectors/`, and `server/`). Relevant whenever running or adding checks in those components.
Read the top-level `.kb/agents.md` file before continuing below.


# Important

- Each subproject (`agent/`, `cli/`, `common/`, `device-connectors/`, `server/`) manages its own dependencies with `uv`; run `uv sync` inside a component directory before working on it in isolation.
- `just` is the task runner, with a modular justfile per component plus one at the repository root. Run `just` from any directory to list the recipes available there, or `just <component>::<recipe>` from the root to target a specific component.
- The common recipes across components are `just format`, `just lint`, `just test`, and `just check` (runs format, lint, and test together; the root `just check` also lints GitHub workflows with `zizmor`).
- Install git hooks with `just pre-commit` (uses `prek` to support the monorepo layout).
- Prefer running the narrowest applicable `just check`/`just test` for the component you changed before considering work done.
- Documentation uses separate `just` recipes that delegate to Make; read `docs/AGENTS.md` when changing it.
