# Integration Test Framework

## Overview

Integration tests for verifying that the agents, server and cli correctly work together.

## Test Preconditions

**All tests require:**
1. A running Testflinger server with v2 API (default: http://localhost:5000)
2. A running agent instance (e.g., `just agent start fake_connector test_agent`)
3. The local branch must have the update CLI matching the server API

**Authentication:** Tests use credentials from `sample_users.py` (admin and agent roles)

## Running Tests

### Quick Start

```bash
# Terminal 1: Start server (already running or run your own)
cd /path/to/server-branch
just workshop serve && just workshop populate

# Terminal 2: Start agent
cd /path/to/agent-branch
just agent start fake_connector test_agent

# Terminal 3: Run tests
cd /path/to/cli-branch/
just integration test
```

## Authentication

Tests automatically use credentials from `sample_users.py`:
- **Agent operations** (posting mode): Uses agent client (`infra-agent-arm` or similar)
- **Admin operations** (commanding restart): Uses admin client
- **All credentials**: `secret_key: "testflinger"` (from server/devel/sample_users.py)

## Known Limitations

| Aspect | Status | Details |
|--------|--------|---------|
| Manual server startup | Manual | Tests assume server already running |
| Manual agent startup | Manual | Tests assume agent already running |
| Test data cleanup | None | Tests leave data on server; no cleanup |
| Service account setup | Auto | Uses sample_users.py from server component |

## Architecture

### conftest.py
Provides fixtures:
- `server_url` - Base URL of running server (from `TESTFLINGER_SERVER` env var, default: `http://localhost:5000`)
- `test_agent_name` - Agent under test (default: `test_agent`)
- `api_client` - APIClient with helper methods for different roles:
  - `get_agent(name, role)` → GET /v2/agents/{name}/data
  - `post_agent_mode(name, mode, role)` → POST /v2/agents/{name}/data
  - `patch_commanded_mode(name, mode, role)` → PATCH /v2/agents/{name}/commanded_mode
