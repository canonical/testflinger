# Proposal: Server-side Distro Support

## Problem
Agents do not publish images, so enforcing image validation against the server's advertised list is not viable. The server should allow jobs with any image/distro, and only reject if truly unsupported.

## Recommendation
- Do not require agents to advertise images for a queue.
- Accept any image/distro in job requests; only reject if the agent cannot handle it.
- Optionally, add a `/v1/agents/distros` endpoint for agents that wish to advertise supported distros, but do not enforce this for job acceptance.

## Rationale
- Increases flexibility for new distros and images.
- Matches real-world agent/server usage.
- Reduces user friction and support burden.
