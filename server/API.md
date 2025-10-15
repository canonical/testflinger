# Testflinger Server API

## `[POST] /v1/job`

Create a test job request and place it on the specified queue

Most parameters passed in the data section of this API will be specific to the
type of agent receiving them. The `job_queue` parameter is used to designate the
queue used, but all others will be passed along to the agent.

Parameters:

- `job_queue` (JSON): queue name to use for processing the job

Returns:

```json
{ "job_id": "<job_id (UUID)>" }
```

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 422 (Unprocessable Content)`: The submitted job contains references to secrets and these secrets are, for any reason, inaccessible.

Examples:

```shell
curl http://localhost:8000/v1/job -X POST \
  --header "Content-Type: application/json" \
  --data '{ "job_queue": "myqueue", "option":"foo" }'
```

## `[GET] /v1/job`

Get a test job from the specified queue(s)

When an agent wants to request a job for processing, it can make this request
along with a list of one or more queues that it is configured to process. The
server will only return one job.

Parameters:

`queue` (multivalue): queue name(s) that the agent can process

Returns:

JSON job data that was submitted by the requestor, or nothing if no jobs in the
specified queue(s) are available.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: this is returned if no queue is specified
- `HTTP 204 (NO DATA)`: if there are no jobs in the specified queues

Example:

```shell
curl http://localhost:8000/v1/job?queue=foo\&queue=bar
```

> [!NOTE]
> Any secrets that are referenced in the job are "resolved" when
> the job is retrieved by an agent through this endpoint. Any secrets
> that are inaccessible at the time of retrieval will be resolved to the
> empty string.

## `[GET] /v1/job/search`

Search for jobs by tag(s) and state(s)

Parameters:

- `tags` (array): List of string tags to search for
- `match` (string): Match mode for
- `tags` (string, "all" or "any", default: "any")
- `state` (array): List of job states to include (or "active" to search all
  states other than cancelled and completed)

Returns:

Array of matching jobs

Example:

```shell
curl 'http://localhost:8000/v1/job/search?tags=foo&tags=bar&match=all'
```

This will find jobs tagged with both "foo" and "bar".

## `[POST] /v1/result/<job_id>`

Post job outcome data for the specified job_id

Parameters:

- `job_id` (UUID): test job identifier

Request Body:

- `status` (object): Dictionary mapping phase names to exit codes
- `device_info` (object, optional): Device information
- `job_state` (string, optional): Current job state

Status Codes:

- `HTTP 200 (OK)`

Example:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000 \
  -X POST --header "Content-Type: application/json" \
  --data '{ "status": {"setup": 0, "provision": 0, "test": 0}, "device_info": {} }'
```

## `[GET] /v1/result/<job_id>`

Return previously submitted job outcome data

This endpoint reconstructs results from the new logging system to maintain backward compatibility. It combines phase status information with logs to provide a complete view of job results.

Parameters:

- `job_id` (UUID): test job identifier

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (NO DATA)`: if there are no results for that ID yet

Returns:

JSON data with flattened structure including:
- `{phase}_status`: Exit code for each phase
- `{phase}_output`: Standard output logs for each phase (if available)
- `{phase}_serial`: Serial console logs for each phase (if available)
- Additional metadata fields (device_info, job_state, etc.)

Example:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000 -X GET
```

## `[POST] /v1/result/<job_id>/log/<log_type>`

Post a log fragment for the specified job_id and log type

This is the new logging endpoint that agents use to stream log data in fragments. Each fragment includes metadata for tracking and querying.

Parameters:

- `job_id` (UUID): test job identifier
- `log_type` (string): Type of log - either `output` or `serial`

Request Body:

- `fragment_number` (integer): Sequential fragment number starting from 0
- `timestamp` (string): ISO 8601 timestamp when the fragment was created
- `phase` (string): Test phase name (setup, provision, firmware_update, test, allocate, reserve, cleanup)
- `log_data` (string): The log content for this fragment

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: Invalid log_type or missing required fields

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

Retrieve logs for the specified job_id and log type

This endpoint supports querying logs with optional filtering by phase, fragment number, or timestamp. Logs are persistent and can be retrieved multiple times.

Parameters:

- `job_id` (UUID): test job identifier
- `log_type` (string): Type of log - either `output` or `serial`

Query Parameters (all optional):

- `phase` (string): Filter logs to a specific test phase
- `start_fragment` (integer): Return only fragments from this number onwards
- `start_timestamp` (string): Return only logs created after this ISO 8601 timestamp

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (NO DATA)`: if there are no logs for that ID yet
- `HTTP 400 (Bad Request)`: Invalid log_type or query parameters

Returns:

JSON object with logs organized by phase. Each phase includes:
- `last_fragment_number`: The highest fragment number for this phase
- `log_data`: Combined log text from all matching fragments

Example:

```shell
# Get all output logs for a job
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/log/output

# Get only setup phase output logs
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/log/output?phase=setup

# Get logs from fragment 5 onwards
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/log/output?start_fragment=5

# Get logs after a specific timestamp
curl "http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/log/output?start_timestamp=2025-10-15T10:30:00Z"
```

Response example:

```json
{
  "output": {
    "setup": {
      "last_fragment_number": 5,
      "log_data": "Starting setup...\nSetup complete\n"
    },
    "provision": {
      "last_fragment_number": 12,
      "log_data": "Provisioning device...\nDevice ready\n"
    }
  }
}
```

## `[POST] /v1/result/<job_id>/artifact`

Upload a file artifact for the specified job_id

Parameters:

- `job_id` (UUID): test job identifier

Status Codes:

- `HTTP 200 (OK)`

Example:

```shell
curl -X POST -F "file=@README.rst" localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/artifact
```

## `[GET] /v1/result/<job_id>/artifact`

Download previously submitted artifact for this job

Parameters:

- `job_id` (UUID): test job identifier

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (NO DATA)`: if there are no results for that ID yet

Returns:

JSON data previously submitted to this job_id via the POST API

Example:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/artifact \
  -X GET -O artifact.tar.gz
```

## `[POST] /v1/agents/queues`

Post names/descriptions of queues serviced by this agent

Status Codes:

- `HTTP 200 (OK)`

Example:

```shell
curl http://localhost:8000/v1/agents/queues \
  -X POST --header "Content-Type: application/json" \
  --data '{ "myqueue": "queue 1", "myqueue2": "queue 2" }'
```

## `[GET] /v1/agents/queues`

Retrieve the list of well-known queues

Status Codes:

- `HTTP 200 (OK)`

Returns:

JSON data previously submitted by all agents via the POST API

Example:

```shell
curl http://localhost:8000/v1/agents/queues -X GET
```

## `[POST] /v1/agents/images`

Post known images for the specified queue

Status Codes:

- `HTTP 200 (OK)`

Example:

```shell
curl http://localhost:8000/v1/agents/images \
  -X POST --header "Content-Type: application/json" \
  --data '{ "myqueue": { "image1": "url: http://place/imgae1" }}'
```

## `[GET] /v1/agents/images/<queue>`

Retrieve all known image names and the provisioning data used for them, for the
specified queue

Parameters:

- `queue`: name of the queue to use

Status Codes:

- `HTTP 200 (OK)`

Returns:

JSON data previously submitted by all agents via the POST API

Example:

```shell
curl http://localhost:8000/v1/agents/images/myqueue -X GET
```

## `[POST] /v1/job/<job_id>/action`

Execute action for the specified `job_id`

Parameters:

- `job_id` (UUID): test job identifier

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: The job is already completed or cancelled
- `HTTP 404 (Not Found)`: The job isn't found
- `HTTP 422 (Unprocessable)`: The action or the argument to it could not be processed

Supported Actions:

- `Cancel`: cancel a job that hasn't been completed yet

Example:

```shell
curl http://localhost:8000/v1/job/00000000-0000-0000-0000-000000000000/action \
  -X POST --header "Content-Type: application/json" \
  --data '{ "action":"cancel" }'
```

## `[GET] /v1/agents/data`

Retrieve all agent data

Status Codes:

- `HTTP 200 (OK)`

Returns:

JSON data for all known agents, useful for external systems that need to gather
this information

Example:

```shell
curl -X GET http://localhost:8000/v1/agents/data
```

## `[GET] /v1/agents/data/<agent_name>`

Retrieve data from a specified agent. 

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`: The agent isn't found

Returns:

JSON data for specified agent, useful for getting information from a
single agent. 

Example:

```shell
curl -X GET http://localhost:8000/v1/agents/data/foo
```

## `[POST] /v1/agents/provision_logs/<agent_name>`

Post provision log data for the specified agent

Status Codes:

- `HTTP 200 (OK)`

Example:

```shell
curl http://localhost:8000/v1/agents/provision_logs/myagent \
  -X POST --header "Content-Type: application/json" \
  --data '{ "job_id": "00000000-0000-0000-0000-000000000000", \
            "exit_code": 1, "detail":"foo" }'
```

## `[POST] /v1/job/<job_id>/events`

Receive job status updates from an agent and posts them to the specified webhook.

The `job_status_webhook` parameter is required for this endpoint. Other
parameters included here will be forwarded to the webhook.

Parameters:

- `job_id` (UUID): test job identifier
- `job_status_webhook`: webhook URL to post status updates to

Returns:

Text response from the webhook if the server was successfully able to post.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad request)`: The arguments could not be processed by the server
- `HTTP 504 (Gateway Timeout)`: The webhook URL timed out

Example:

```shell
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "agent-00", "job_queue": "myqueue", "job_status_webhook": "http://mywebhook", "events": [{"event_name": "started_provisioning", "timestamp": "2024-05-03T19:11:33.541130+00:00", "detail": "my_detailed_message"}]}' http://localhost:8000/v1/job/00000000-0000-0000-0000-000000000000/events
```

## `[GET] /v1/queues/wait_times`

Get wait time metrics - optionally take a list of queues

Parameters:

- `queue` (array): list of queues to get wait time metrics for

Returns:

JSON mapping of queue names to wait time metrics

Example:

```shell
curl http://localhost:8000/v1/queues/wait_times?queue=foo\&queue=bar
```

## `[GET] /v1/queues/<queue_name>/agents`

Get the list of agents listening to a specified queue

Parameters:

- `queue_name` (string): name of the queue for which to get the agents that are listening to it

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (NO DATA)`: if there are no agents in the specified queue. 
- `HTTP 404 (NOT FOUND)`: if the queue does not exists. 

Returns:

JSON array of agents listening to the specified queue

Example:

```shell
curl http://localhost:8000/v1/queues/foo/agents
```

## `[GET] /v1/queues/<queue_name>/jobs`

Search for jobs in a specified queue. 

Parameters:

`queue_name` (string): queue name(s) where to get the jobs. 

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (NO DATA)`: if there are no jobs in the specified queue. 

Returns:

JSON job data with information about the ID, creation time and state for jobs in the specified queue. 

Example:

```shell
curl 'http://localhost:8000/v1/queues/foo/jobs'
```

This will find jobs in the queue `foo` and return its IDs, creation time and state. 

## `[POST] /v1/oauth2/token`

Authenticate a client and return an access token and refresh token.

Headers:

- Basic Authorization: client_id:client_key (Base64 Encoded)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: invalid client_id or client-key

Returns:

```json
{
  "access_token": "<JWT access token>",
  "token_type": "Bearer",
  "expires_in": 30,
  "refresh_token": "<opaque refresh token>",
}
```

Notes:
- `expires_in` is the lifetime (in seconds) of the access token.
- Refresh tokens default to 30 days; admin may issue non-expiring tokens for trusted integrations.

Example:

```shell
curl http://localhost:8000/v1/oauth2/token \
  -X POST --header "Authorization: Basic ABCDEF12345"
```

## `[POST] /v1/oauth2/refresh`

Exchange a valid refresh token for a new access token.

Parameters (JSON body):

- `token` (string): The opaque refresh token issued earlier.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: missing, invalid, revoked or expired refresh token

Returns:

```json
{
  "access_token": "<new JWT access token>",
  "token_type": "Bearer",
  "expires_in": 30
}
```

Example:

```shell
curl http://localhost:8000/v1/oauth2/refresh \
  -X POST --header "Content-Type: application/json" \
  --data '{"refresh_token": "opaque-refresh-token"}'
```

## `[POST] /v1/oauth2/revoke`

Revoke a refresh token so it can no longer be used.

Parameters (JSON body):

- `token` (string): The opaque refresh token to revoke.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: invalid request

Returns:

```json
{
  "message": "Refresh token revoked successfully"
}
```

Example:

```shell
curl http://localhost:8000/v1/oauth2/revoke \
  -X POST --header "Content-Type: application/json" \
  --data '{"refresh_token": "opaque-refresh-token"}'
```

## `[GET] /v1/restricted-queues`

Retrieve the list of all restricted queues and their owners.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user

Returns:

JSON data with a list of restricted queues

Example:

```shell
curl http://localhost:8000/v1/restricted-queues \
  -X GET --header "Authorization: Bearer <JWT Token>"
```

## `[GET] /v1/restricted-queues/<queue_name>`

Retrieve the specified restricted queue and its owners.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user

Returns:

JSON data with restricted queue and who owns it

Example:

```shell
curl http://localhost:8000/v1/restricted-queues/foo \
  -X GET --header "Authorization: Bearer <JWT Token>"
```

## `[POST] /v1/restricted-queues/<queue_name>`

Add an owner to the specific restricted queue.
If the queue does not exist yet, it will be created automatically.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: Missing client_id to set as owner of restricted queue.
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 404 (Not Found)`: Queue does not exists or is not associated to an agent.

Example:

```shell
curl http://localhost:8000/v1/restricted-queues/foo \
  -X POST --header "Authorization: Bearer <JWT Token>" \
  --header "Content-Type: application/json" \
  --header "Accept: application/json" \
  --data '{"client_id": "foo"}'
```

## `[DELETE] /v1/restricted-queues/<queue_name>`

Delete an owner from the specific restricted queue.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: Missing client_id to set as owner of restricted queue.
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 404 (Not Found)`: Queue is not in the restricted queue list

Example:

```shell
curl http://localhost:8000/v1/restricted-queues/foo \
  -X DELETE --header "Authorization: Bearer <JWT Token>" \
  --header "Content-Type: application/json" \
  --header "Accept: application/json" \
  --data '{"client_id": "foo"}'
```

## `[GET] /v1/client-permissions`

Retrieve the list all client_id and its permissions

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user

Returns:

JSON data with a list all client IDs and its permission excluding the hashed secret stored in database

Example:

```shell
curl http://localhost:8000/v1/client-permissions \
  -X GET --header "Authorization: Bearer <JWT Token>"
```

## `[GET] /v1/client-permissions/<client_id>`

Retrieve the permissions associated with a client_id

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 404 (Not Found)`: Specified client_id does not exist

Returns:

JSON data with the permissions of a specified client excluding the hashed secret stored in database

Example:

```shell
curl http://localhost:8000/v1/client-permissions/foo \
  -X GET --header "Authorization: Bearer <JWT Token>"
```

## `[POST] /v1/client-permissions`

Create new client_id with specified permissions.

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 400 (Bad Request)`: Missing client_id and/or client_secret in JSON data
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 409 (Conflict)`: Specified client_id already exists

Example:

```shell
curl http://localhost:8000/v1/client-permissions \
  -X POST --header "Authorization: Bearer <JWT Token>"
  --header "Content-Type: application/json" \
  --header "Accept: application/json" \
  --data '{"client_id": "foo", "client_secret": "my-secret-password", "max_priority": {}, "max_reservation_time": {"*": 40000}, "role": "contributor"}'
```

## `[PUT] /v1/client-permissions/<client_id>`

Edit the permissions for a specified client_id. 

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 404 (Not Found)`: Specified client_id does not exist

Example:

```shell
curl http://localhost:8000/v1/client-permissions/foo \
  -X PUT --header "Authorization: Bearer <JWT Token>"
  --header "Content-Type: application/json" \
  --header "Accept: application/json" \
  --data '{"max_priority": {"q1": 10}, "max_reservation_time": {}, "role": "contributor"}'
```

## `[DELETE] /v1/client-permissions/<client_id>`

Delete a client_id along with its permissions

Headers:

- Bearer Token: JWT Token with permissions (Base64 Encoded)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key
- `HTTP 403 (Forbidden)`: Incorrect permissions for authenticated user
- `HTTP 404 (Not Found)`: Specified client_id does not exist
- `HTTP 422 (Unprocessable Entity)`: System admin can't be removed using the API

Example:

```shell
curl http://localhost:8000/v1/client-permissions/foo \
  -X DELETE --header "Authorization: Bearer <JWT Token>"
```