# Testflinger API

## `[GET] /v1/`

Identify ourselves.

Status Codes:

- `HTTP 200 (OK)`

## `[GET] /v1/agents/data`

Retrieve all agent data.

Returns JSON data for all known agents, useful for external systems that
need to gather this information.

Returns:

JSON data matching the `AgentOut` schema.

Status Codes:

- `HTTP 200 (OK)`

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl -X GET http://localhost:8000/v1/agents/data
```

## `[POST] /v1/agents/data/<agent_name>`

Post information about the agent to the server.

The data may include the device state, the queues it is listening on,
its location, the job_id it is running (if any), and recent log lines.

Parameters:

- `agent_name` (string, path)

Request Body:

- `comment` (string, optional)
- `identifier` (string, optional)
- `job_id` (string, optional)
- `location` (string, optional)
- `log` (array of string, optional)
- `provision_type` (string, optional)
- `queues` (array of string, optional)
- `state` (string, optional)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

Required roles: `admin`, `manager`, `agent`

## `[GET] /v1/agents/data/<agent_name>`

Retrieve data from a specified agent.

Returns JSON data for the specified agent, useful for getting information
from a single agent.

Parameters:

- `agent_name` (string, path)

Returns:

JSON data matching the `AgentOut` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`: The agent isn't found

Required roles: `admin`, `manager`, `contributor`, `agent`

Example:

```shell
curl -X GET http://localhost:8000/v1/agents/data/foo
```

## `[POST] /v1/agents/images`

Post known images for the specified queue.

Images are stored as image_name:provision_data mappings within the queues
collection, keyed by queue name.

Status Codes:

- `HTTP 200 (OK)`

Required roles: `admin`, `manager`, `agent`

Example:

```shell
curl http://localhost:8000/v1/agents/images \
  -X POST --header "Content-Type: application/json" \
  --data '{ "myqueue": { "image1": "url: http://place/image1" }}'
```

## `[GET] /v1/agents/images/<queue>`

Retrieve all known image names and the provisioning data used for them.

Returns the JSON data, for the specified queue, previously submitted by
all agents via the POST API.

Parameters:

- `queue` (string, path)

Returns:

```json
{
  "core22": "url: http://.../core22.img.xz",
  "server-22.04": "url: http://.../ubuntu-22.04.img.xz"
}
```

Status Codes:

- `HTTP 200 (OK)`: Mapping of image names and provision data
- `HTTP 404 (Not Found)`

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl http://localhost:8000/v1/agents/images/myqueue -X GET
```

## `[POST] /v1/agents/provision_logs/<agent_name>`

Post provision log data for the specified agent.

Parameters:

- `agent_name` (string, path)

Request Body:

- `detail` (string, optional)
- `exit_code` (integer)
- `job_id` (string)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

Required roles: `agent`

Example:

```shell
curl http://localhost:8000/v1/agents/provision_logs/myagent \
  -X POST --header "Content-Type: application/json" \
  --data '{ "job_id": "00000000-0000-0000-0000-000000000000", \
            "exit_code": 1, "detail":"foo" }'
```

## `[POST] /v1/agents/queues`

Post names/descriptions of queues serviced by this agent.

Some agents may want to advertise some of the queues they listen on so
that the user can check which queues are valid to use.

Status Codes:

- `HTTP 200 (OK)`

Required roles: `admin`, `manager`, `agent`

Example:

```shell
curl http://localhost:8000/v1/agents/queues \
  -X POST --header "Content-Type: application/json" \
  --data '{ "myqueue": "queue 1", "myqueue2": "queue 2" }'
```

## `[GET] /v1/agents/queues`

Retrieve the list of well-known queues.

Returns the JSON data previously submitted by all agents via the POST
API, as a mapping of queue names to descriptions.

Returns:

```json
{
  "device001": "Queue for device001",
  "some-queue": "some other queue"
}
```

Status Codes:

- `HTTP 200 (OK)`: Mapping of queue names and descriptions

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl http://localhost:8000/v1/agents/queues -X GET
```

## `[GET] /v1/client-permissions`

Retrieve the list of all client_id and their permissions.

Returns JSON data with a list of all client IDs and their permissions,
excluding the hashed secret stored in the database.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Returns:

JSON data matching the `ClientPermissionsOut` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user

Required roles: `admin`, `manager`

Example:

```shell
curl http://localhost:8000/v1/client-permissions \
  -X GET --header "Authorization: Bearer <JWT Token>"
```

## `[GET] /v1/client-permissions/<client_id>`

Retrieve the permissions associated with a client_id.

Returns JSON data with the permissions of the specified client, excluding
the hashed secret stored in the database.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Parameters:

- `client_id` (string, path)

Returns:

JSON data matching the `ClientPermissionsOut` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 404 (Not Found)`: Specified client_id does not exist

Required roles: `admin`, `manager`

Example:

```shell
curl http://localhost:8000/v1/client-permissions/foo \
  -X GET --header "Authorization: Bearer <JWT Token>"
```

## `[PUT] /v1/client-permissions/<client_id>`

Edit the permissions for a specified client_id.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Parameters:

- `client_id` (string, path)

Request Body:

- `client_secret` (string, optional)
- `max_priority` (object, optional)
- `max_reservation_time` (object, optional)
- `role` (string, optional)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 404 (Not Found)`: Specified client_id does not exist
- `HTTP 422 (Unprocessable Entity)`: Validation error

Required roles: `admin`, `manager`

Example:

```shell
curl http://localhost:8000/v1/client-permissions/foo \
  -X PUT --header "Authorization: Bearer <JWT Token>"
  --header "Content-Type: application/json" \
  --header "Accept: application/json" \
  --data '{"max_priority": {"q1": 10}, "max_reservation_time": {}, "role": "contributor"}'
```

## `[DELETE] /v1/client-permissions/<client_id>`

Delete a client_id along with its permissions.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Parameters:

- `client_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 404 (Not Found)`: Specified client_id does not exist
- `HTTP 422 (Unprocessable Entity)`: System admin can't be removed using the API

Required roles: `admin`

Example:

```shell
curl http://localhost:8000/v1/client-permissions/foo \
  -X DELETE --header "Authorization: Bearer <JWT Token>"
```

## `[POST] /v1/job`

Create a test job request and place it on the specified queue.

Most parameters passed in the data section of this API will be specific
to the type of agent receiving them. The `job_queue` parameter is used to
designate the queue used, but all others will be passed along to the
agent.

Request Body:

- `allocate_data` (object, optional)
- `allocation_timeout` (integer, optional)
- `debug` (boolean, optional)
- `exclude_agents` (array of string, optional)
- `firmware_update_data` (object, optional)
- `global_timeout` (integer, optional)
- `job_id` (string, optional)
- `job_priority` (integer, optional)
- `job_queue` (string)
- `job_status_webhook` (string, optional)
- `name` (string, optional)
- `output_timeout` (integer, optional)
- `parent_job_id` (string, optional)
- `provision_data` (object, optional)
- `reserve_data` (ReserveData, optional)
- `tags` (array of string, optional)
- `test_data` (TestData, optional)

Returns:

```json
{
  "job_id": "<job_id (UUID)>"
}
```

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 422 (Unprocessable Entity)`: The submitted job contains references to secrets and these secrets are, for any reason, inaccessible.

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl http://localhost:8000/v1/job -X POST \
  --header "Content-Type: application/json" \
  --data '{ "job_queue": "myqueue", "option":"foo" }'
```

## `[GET] /v1/job`

Get a test job from the specified queue(s).

When an agent wants to request a job for processing, it can make this
request along with a list of one or more queues that it is configured to
process. The server will only return one job.

Returns JSON job data that was submitted by the requestor, or nothing if
no jobs in the specified queue(s) are available.

Parameters:

- `queue` (array of string, query, optional): Queue name(s) that the agent can process

Returns:

JSON data matching the `Job` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (No Content)`: No jobs in the specified queue(s)
- `HTTP 400 (Bad Request)`: No queue is specified
- `HTTP 422 (Unprocessable Entity)`: Validation error

Required roles: `agent`

> [!NOTE]
> Any secrets that are referenced in the job are "resolved" when the job is retrieved by an agent through this endpoint. Any secrets that are inaccessible at the time of retrieval will be resolved to the empty string.

Example:

```shell
curl http://localhost:8000/v1/job?queue=foo\&queue=bar
```

## `[GET] /v1/job/search`

Search for jobs by tag(s) and state(s).

The example below finds jobs tagged with both "foo" and "bar".

Parameters:

- `tags` (array of string, query, optional): List of tags to search for
- `match` (string, query, optional): Match mode - 'all' or 'any' (default 'any')
- `state` (array of string, query, optional): List of job states to include

Returns:

JSON data matching the `JobSearchResponse` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl 'http://localhost:8000/v1/job/search?tags=foo&tags=bar&match=all'
```

## `[GET] /v1/job/<job_id>`

Get the JSON job definition for a specified job.

Returns the job definition even if it has already run.

Parameters:

- `job_id` (string, path)

Returns:

JSON data matching the `Job` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

Required roles: `admin`, `manager`, `contributor`

## `[POST] /v1/job/<job_id>/action`

Execute action for the specified job_id.

Supported actions:

- `cancel`: cancel a job that hasn't been completed yet

Parameters:

- `job_id` (string, path)

Request Body:

- `action` (string)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: The job is already completed or cancelled
- `HTTP 404 (Not Found)`: The job isn't found
- `HTTP 422 (Unprocessable Entity)`: The action or the argument to it could not be processed

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl http://localhost:8000/v1/job/00000000-0000-0000-0000-000000000000/action \
  -X POST --header "Content-Type: application/json" \
  --data '{ "action":"cancel" }'
```

## `[POST] /v1/job/<job_id>/attachments`

Post attachment bundle for a specified job_id.

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

Required roles: `admin`, `manager`, `contributor`

## `[GET] /v1/job/<job_id>/attachments`

Return the attachments bundle for a specified job_id.

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

Required roles: `agent`

## `[POST] /v1/job/<job_id>/events`

Receive job status updates from an agent and post them to a webhook.

The `job_status_webhook` parameter is required for this endpoint. Other
parameters included here will be forwarded to the webhook.

Returns the text response from the webhook if the server was successfully
able to post.

Parameters:

- `job_id` (string, path)

Request Body:

- `agent_id` (string, optional)
- `events` (array of JobEvent, optional)
- `job_queue` (string, optional)
- `job_status_webhook` (string)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: The arguments could not be processed by the server
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error
- `HTTP 504 (Gateway Timeout)`: The webhook URL timed out

Required roles: `agent`

Example:

```shell
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent-00", "job_queue": "myqueue", "job_status_webhook": "http://mywebhook", "events": [{"event_name": "started_provisioning", "timestamp": "2024-05-03T19:11:33.541130+00:00", "detail": "my_detailed_message"}]}' http://localhost:8000/v1/job/00000000-0000-0000-0000-000000000000/events
```

## `[GET] /v1/job/<job_id>/position`

Return the position of the specified jobid in the queue.

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

Required roles: `admin`, `manager`, `contributor`

## `[POST] /v1/oauth2/refresh`

Exchange a valid refresh token for a new access token.

Expects a JSON body with a `refresh_token` (string): the opaque refresh
token issued earlier.

Returns:

```json
{
  "access_token": "<new JWT access token>",
  "expires_in": 30,
  "token_type": "Bearer"
}
```

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: Missing, invalid, revoked or expired refresh token

Example:

```shell
curl http://localhost:8000/v1/oauth2/refresh \
  -X POST --header "Content-Type: application/json" \
  --data '{"refresh_token": "opaque-refresh-token"}'
```

## `[POST] /v1/oauth2/revoke`

Revoke a refresh token so it can no longer be used.

Expects a JSON body with a `token` (string): the opaque refresh token to
revoke. Only admins can perform this action.

Returns:

```json
{
  "message": "Refresh token revoked successfully"
}
```

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: Invalid request

Required roles: `admin`

Example:

```shell
curl http://localhost:8000/v1/oauth2/revoke \
  -X POST --header "Content-Type: application/json" \
  --data '{"refresh_token": "opaque-refresh-token"}'
```

## `[POST] /v1/oauth2/token`

Authenticate a client and return an access token and refresh token.

Headers:

- Basic Authorization: client_id:client_key (Base64 Encoded)

Returns:

```json
{
  "access_token": "<JWT access token>",
  "expires_in": 30,
  "refresh_token": "<opaque refresh token>",
  "token_type": "Bearer"
}
```

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key

> [!NOTE]
> `expires_in` is the lifetime (in seconds) of the access token.

> [!NOTE]
> Refresh tokens default to 30 days; admin may issue non-expiring tokens for trusted integrations.

Example:

```shell
curl http://localhost:8000/v1/oauth2/token \
  -X POST --header "Authorization: Basic ABCDEF12345"
```

## `[GET] /v1/queues/wait_times`

Get wait time metrics - optionally take a list of queues.

Accepts an optional `queue` (array) query parameter listing the queues to
get wait time metrics for. Returns a JSON mapping of queue names to wait
time metrics.

Status Codes:

- `HTTP 200 (OK)`

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl http://localhost:8000/v1/queues/wait_times?queue=foo\&queue=bar
```

## `[GET] /v1/queues/<queue_name>/agents`

Get the list of agents listening to a specified queue.

Returns a JSON array of agents listening to the specified queue.

Parameters:

- `queue_name` (string, path)

Returns:

JSON data matching the `AgentOut` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (No Content)`: No agents in the specified queue
- `HTTP 404 (Not Found)`: The queue does not exist

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl http://localhost:8000/v1/queues/foo/agents
```

## `[GET] /v1/queues/<queue_name>/jobs`

Search for jobs in a specified queue.

Returns JSON job data with information about the ID, creation time and
state for jobs in the specified queue.

Parameters:

- `queue_name` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (No Content)`: No jobs in the specified queue
- `HTTP 404 (Not Found)`

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl 'http://localhost:8000/v1/queues/foo/jobs'
```

## `[GET] /v1/restricted-queues`

Retrieve the list of all restricted queues and their owners.

Returns JSON data with a list of restricted queues.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Returns:

JSON data matching the `RestrictedQueueOut` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl http://localhost:8000/v1/restricted-queues \
  -X GET --header "Authorization: Bearer <JWT Token>"
```

## `[POST] /v1/restricted-queues/<queue_name>`

Add an owner to the specific restricted queue.

If the queue does not exist yet, it will be created automatically.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Parameters:

- `queue_name` (string, path)

Request Body:

- `client_id` (string)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: Missing client_id to set as owner of restricted queue
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 404 (Not Found)`: Queue does not exist or is not associated to an agent
- `HTTP 422 (Unprocessable Entity)`: Validation error

Required roles: `admin`, `manager`

Example:

```shell
curl http://localhost:8000/v1/restricted-queues/foo \
  -X POST --header "Authorization: Bearer <JWT Token>" \
  --header "Content-Type: application/json" \
  --header "Accept: application/json" \
  --data '{"client_id": "foo"}'
```

## `[GET] /v1/restricted-queues/<queue_name>`

Retrieve the specified restricted queue and its owners.

Returns JSON data with the restricted queue and who owns it.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Parameters:

- `queue_name` (string, path)

Returns:

JSON data matching the `RestrictedQueueOut` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 404 (Not Found)`

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl http://localhost:8000/v1/restricted-queues/foo \
  -X GET --header "Authorization: Bearer <JWT Token>"
```

## `[DELETE] /v1/restricted-queues/<queue_name>`

Delete an owner from the specific restricted queue.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Parameters:

- `queue_name` (string, path)

Request Body:

- `client_id` (string)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: Missing client_id to set as owner of restricted queue
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 404 (Not Found)`: Queue is not in the restricted queue list
- `HTTP 422 (Unprocessable Entity)`: Validation error

Required roles: `admin`, `manager`

Example:

```shell
curl http://localhost:8000/v1/restricted-queues/foo \
  -X DELETE --header "Authorization: Bearer <JWT Token>" \
  --header "Content-Type: application/json" \
  --header "Accept: application/json" \
  --data '{"client_id": "foo"}'
```

## `[POST] /v1/result/<job_id>`

Post job outcome data for the specified job_id.

Parameters:

- `job_id` (string, path)

Request Body:

- `device_info` (object, optional)
- `job_state` (string, optional)
- `status` (object, optional)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

Required roles: `agent`

Example:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000 \
  -X POST --header "Content-Type: application/json" \
  --data '{ "status": {"setup": 0, "provision": 0, "test": 0}, "device_info": {} }'
```

## `[GET] /v1/result/<job_id>`

Return previously submitted job outcome data.

This endpoint reconstructs results from the new logging system to
maintain backward compatibility. It combines phase status information
with logs to provide a complete view of job results.

Returns JSON data with a flattened structure including:

- `{phase}_status`: Exit code for each phase
- `{phase}_output`: Standard output logs for each phase (if available)
- `{phase}_serial`: Serial console logs for each phase (if available)
- Additional metadata fields (device_info, job_state, etc.)

Parameters:

- `job_id` (string, path)

Returns:

JSON data matching the `ResultGet` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (No Content)`: No results for that job_id yet
- `HTTP 404 (Not Found)`

Required roles: `admin`, `manager`, `contributor`, `agent`

Example:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000 -X GET
```

## `[POST] /v1/result/<job_id>/artifact`

Upload a file artifact for the specified job_id.

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

Required roles: `agent`

Example:

```shell
curl -X POST -F "file=@README.rst" localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/artifact
```

## `[GET] /v1/result/<job_id>/artifact`

Download previously submitted artifact for this job.

Returns the JSON data previously submitted to this job_id via the POST
API.

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (No Content)`: No results for that job_id yet
- `HTTP 404 (Not Found)`

Required roles: `admin`, `manager`, `contributor`

Example:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/artifact \
  -X GET -O artifact.tar.gz
```

## `[POST] /v1/result/<job_id>/log/<log_type>`

Post a log fragment for the specified job_id and log type.

This is the new logging endpoint that agents use to stream log data in
fragments. Each fragment includes metadata for tracking and querying.

`log_type` is the type of log - either `output` or `serial`.

Parameters:

- `job_id` (string, path)
- `log_type` (string, path)

Request Body:

- `fragment_number` (integer)
- `log_data` (string)
- `phase` (string)
- `timestamp` (string)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: Invalid log_type or missing required fields
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

Required roles: `agent`

Example:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/log/output \
  -X POST --header "Content-Type: application/json" \
  --data '{
    "fragment_number": 0,
    "timestamp": "2025-10-15T10:00:00+00:00",
    "phase": "setup",
    "log_data": "Starting setup phase..."
  }'
```

## `[GET] /v1/result/<job_id>/log/<log_type>`

Retrieve logs for the specified job_id and log type.

This endpoint supports querying logs with optional filtering by phase,
fragment number, or timestamp. Logs are persistent and can be retrieved
multiple times.

`log_type` is the type of log - either `output` or `serial`.

The following optional query parameters are supported:

- `phase` (string): Filter logs to a specific test phase
- `start_fragment` (integer): Return only fragments from this number on
- `start_timestamp` (string): Return only logs created after this ISO
8601 timestamp

Returns a JSON object with logs organized by phase. Each phase includes a
`last_fragment_number` (the highest fragment number for this phase) and
`log_data` (combined log text from all matching fragments).

Parameters:

- `job_id` (string, path)
- `log_type` (string, path)

Returns:

JSON data matching the `LogGet` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (No Content)`: No logs for that job_id yet
- `HTTP 400 (Bad Request)`: Invalid log_type or query parameters
- `HTTP 404 (Not Found)`

Required roles: `admin`, `manager`, `contributor`

Examples:

Get all output logs for a job:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/log/output
```

Get only setup phase output logs:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/log/output?phase=setup
```

Get logs from fragment 5 onwards:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/log/output?start_fragment=5
```

Get logs after a specific timestamp:

```shell
curl "http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/log/output?start_timestamp=2025-10-15T10:30:00Z"
```

## `[PUT] /v1/secrets/<client_id>/<path>`

Store a secret value for the specified client_id and path.

Parameters:

- `client_id` (string, path)
- `path` (string, path)

Request Body:

- `ephemeral` (boolean, optional)
- `expire_after` (integer, optional)
- `value` (string)

Returns:

JSON data matching the `SecretOut` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

Required roles: `contributor`, `manager`, `admin`

## `[DELETE] /v1/secrets/<client_id>/<path>`

Remove a secret value for the specified client_id and path.

Parameters:

- `client_id` (string, path)
- `path` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

Required roles: `contributor`, `manager`, `admin`
