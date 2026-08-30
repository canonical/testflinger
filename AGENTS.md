# Preface

Testflinger is Canonical's distributed test orchestration and lab automation system, structured as a Python monorepo. This file is the top-level index; consult it when navigating the repository or deciding where a change belongs.
Read the top-level `.kb/agents.md` file before continuing below.


# Overview

Testflinger manages time-shared access to a pool of target machines: clients submit jobs to a server-side queue, and per-machine agents pick up and execute those jobs, provisioning and testing devices through device-specific connectors.


# Architecture

See `.kb/architecture.md` for the client-server, job-queue design and how the server, agents, device connectors, CLI, and common library relate.


# Directory

- `agent/` - Per-machine test agent daemon.
- `cli/` - Command-line client for job submission and status.
- `common/` - Shared enums and utilities library.
- `device-connectors/` - Device provisioning and test execution connectors.
- `docs/` - Sphinx documentation site.
- `.github/` - GitHub Actions and CI workflows.
- `.workshop/` - Optional isolated local development environment.
- `server/` - Flask REST API and web UI; job queue backend.
- `justfile` - Root task runner entry point; delegates to per-component justfiles.


# Documents

- `.kb/agents.md` - General rules for the knowledge base reading and writing.
- `.kb/architecture.md` - How the server, agents, device connectors, CLI, and common library fit together.
- `.kb/testing.md` - Cross-component developer workflow: `uv`, `just` recipes, and pre-commit setup.
- `agent/AGENTS.md` - Agent daemon navigation.
- `cli/AGENTS.md` - CLI navigation.
- `common/AGENTS.md` - Shared-library navigation.
- `device-connectors/AGENTS.md` - Device-connector navigation.
- `docs/AGENTS.md` - Documentation-site navigation.
- `server/AGENTS.md` - Server navigation.
