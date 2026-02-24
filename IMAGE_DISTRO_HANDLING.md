# Testflinger CLI and Server: Image/Distro Handling Update

## Summary
- The CLI no longer enforces that images must be advertised by the server.
- Any image or distro can be specified; only server-side rejection will result in an error.
- Agents are not required to publish images for their queues.
- Optionally, agents may advertise supported distros via a new endpoint, but this is not enforced.

## User Impact
- Users can specify any image/distro without encountering local validation errors.
- Only truly unsupported images/distros will be rejected by the server/agent.

## Maintainer Notes
- See `server-distro-support-proposal.md` for rationale and server-side recommendations.
