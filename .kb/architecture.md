# Preface

Explains how the major Testflinger components (server, agents, device connectors, CLI, common) relate to one another around the central job queue. Relevant when reasoning about cross-component behavior or data flow, not for single-component implementation details.
Read the top-level `.kb/agents.md` file before continuing below.


# Architecture

Testflinger is built around a client-server, job-queue model:

- The **server** (`server/`) exposes a REST API and web UI. Clients submit jobs to named queues; the server persists job state in MongoDB and hands out jobs to agents on request.
- **Agents** (`agent/`) are per-machine daemons that poll the server for jobs on the queues they service, execute them against their attached device, and report status and results back to the server.
- **Device connectors** (`device-connectors/`) are invoked by agents to provision, run tests on, and recover the target device.
- The **CLI** (`cli/`) is the primary end-user entry point: it submits jobs to the server, polls for status, streams results, and supports interactive reservation sessions. It is packaged and distributed as a Snap.
- **Common** (`common/`) holds shared enums and utilities (e.g. job/phase states, duration parsing) used by the server and agent to avoid duplication.

Jobs flow: CLI/other client -> server queue -> agent claims job -> agent invokes device connector -> results/status flow back through the agent to the server -> client polls/reads results.
