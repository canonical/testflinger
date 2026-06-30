# Testflinger API

## `[GET] /v1/`

Identify ourselves.

Status Codes:

- `HTTP 200 (OK)`

## `[GET] /v1/agents/data`

Get all agent data.

Returns:

JSON data matching the `AgentOut` schema.

Status Codes:

- `HTTP 200 (OK)`

## `[POST] /v1/agents/data/<agent_name>`

Post information about the agent to the server.

The json sent to this endpoint may contain data such as the following:
{
"state": string, # State the device is in
"queues": array[string], # Queues the device is listening on
"location": string, # Location of the device
"job_id": string, # Job ID the device is running, if any
"log": array[string], # push and keep only the last 100 lines
}

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

## `[GET] /v1/agents/data/<agent_name>`

Get the information from a specified agent.

:param agent_name:
String with the name of the agent to retrieve information from.
:return:
JSON data with the specified agent information.

Parameters:

- `agent_name` (string, path)

Returns:

JSON data matching the `AgentOut` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[POST] /v1/agents/images`

Tell testflinger about known images for a specified queue

images will be stored in a dict of key/value pairs as part of the queues
collection. That dict will contain image_name:provision_data mappings, ex:
{
"some_queue": {
"core22": "http://cdimage.ubuntu.com/.../core-22.tar.gz",
"jammy": "http://cdimage.ubuntu.com/.../ubuntu-22.04.tar.gz"
},
"other_queue": {
...
}
}.

Status Codes:

- `HTTP 200 (OK)`

## `[GET] /v1/agents/images/<queue>`

Get a dict of known images for a given queue.

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

## `[POST] /v1/agents/provision_logs/<agent_name>`

Post provision logs for the agent to the server.

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

## `[POST] /v1/agents/queues`

Tell testflinger the queue names that are being serviced.

Some agents may want to advertise some of the queues they listen on so that
the user can check which queues are valid to use.

Status Codes:

- `HTTP 200 (OK)`

## `[GET] /v1/agents/queues`

Get all advertised queues from this server.

Returns a dict of queue names and descriptions, ex:
{
"some_queue": "A queue for testing",
"other_queue": "A queue for something else"
}

Returns:

```json
{
  "device001": "Queue for device001",
  "some-queue": "some other queue"
}
```

Status Codes:

- `HTTP 200 (OK)`: Mapping of queue names and descriptions

## `[GET] /v1/client-permissions`

Retrieve all client permissions from database.

Returns:

JSON data matching the `ClientPermissionsOut` schema.

Status Codes:

- `HTTP 200 (OK)`

## `[GET] /v1/client-permissions/<client_id>`

Retrieve single client-permissions from database.

Parameters:

- `client_id` (string, path)

Returns:

JSON data matching the `ClientPermissionsOut` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[PUT] /v1/client-permissions/<client_id>`

Add or create client permissions for a specified user.

Parameters:

- `client_id` (string, path)

Request Body:

- `client_secret` (string, optional)
- `max_priority` (object, optional)
- `max_reservation_time` (object, optional)
- `role` (string, optional)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

## `[DELETE] /v1/client-permissions/<client_id>`

Delete client id along with its permissions.

Parameters:

- `client_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[POST] /v1/job`

Add a job to the queue.

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

JSON data matching the `JobId` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

## `[GET] /v1/job`

Request a job to run from supported queues.

Returns:

JSON data matching the `Job` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (No Content)`: No job found

## `[GET] /v1/job/search`

Search for jobs by tags.

Parameters:

- `tags` (array of string, query, optional): List of tags to search for
- `match` (string, query, optional): Match mode - 'all' or 'any' (default 'any')
- `state` (array of string, query, optional): List of job states to include

Returns:

JSON data matching the `JobSearchResponse` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

## `[GET] /v1/job/<job_id>`

Request the json job definition for a specified job, even if it has

already run.

:param job_id:
UUID as a string for the job
:return:
JSON data for the job or error string and http error

Parameters:

- `job_id` (string, path)

Returns:

JSON data matching the `Job` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[POST] /v1/job/<job_id>/action`

Take action on the job status for a specified job ID.

:param job_id:
UUID as a string for the job

Parameters:

- `job_id` (string, path)

Request Body:

- `action` (string)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

## `[POST] /v1/job/<job_id>/attachments`

Post attachment bundle for a specified job_id.

:param job_id:
UUID as a string for the job

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[GET] /v1/job/<job_id>/attachments`

Return the attachments bundle for a specified job_id.

:param job_id:
UUID as a string for the job
:return:
send_file stream of attachment tarball to download

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[POST] /v1/job/<job_id>/events`

Post status updates from the agent to the server to be forwarded

to the server-configured webhook url.

The json sent to this endpoint may contain data such as the following:
{
"agent_id": "<string>",
"job_queue": "<string>",
"job_status_webhook": "<URL as string>",
"events": [
{
"event_name": "<string enum of events>",
"timestamp": "<datetime>",
"detail": "<string>"
},
...
]
}

:param job_id: UUID as a string for the job
:param json_data: JSON data containing the status updates and webhook URL

Parameters:

- `job_id` (string, path)

Request Body:

- `agent_id` (string, optional)
- `events` (array of JobEvent, optional)
- `job_queue` (string, optional)
- `job_status_webhook` (string)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

## `[GET] /v1/job/<job_id>/position`

Return the position of the specified jobid in the queue.

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[POST] /v1/oauth2/refresh`

Refresh access token using a valid refresh token.

Status Codes:

- `HTTP 200 (OK)`

## `[POST] /v1/oauth2/revoke`

Revoke a refresh token. Only admins can perform this action.

Status Codes:

- `HTTP 200 (OK)`

## `[POST] /v1/oauth2/token`

Issue both access token and refresh token for a client.

Get JWT with priority and queue permissions.

Before being encrypted, the JWT can contain fields like:
{
exp: <Expiration DateTime of Token>,
iat: <Issuance DateTime of Token>,
sub: <Subject Field of Token>,
permissions: {
max_priority: <Queue to Priority Level Dict>,
allowed_queues: <List of Allowed Restricted Queues>,
max_reservation_time: <Queue to Max Reservation Time Dict>,
}
}

Status Codes:

- `HTTP 200 (OK)`

## `[GET] /v1/queues/wait_times`

Get wait time metrics - optionally take a list of queues.

Status Codes:

- `HTTP 200 (OK)`

## `[GET] /v1/queues/<queue_name>/agents`

Get the list of all data for agents listening to a specified queue.

Parameters:

- `queue_name` (string, path)

Returns:

JSON data matching the `AgentOut` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[GET] /v1/queues/<queue_name>/jobs`

Get the jobs in a specified queue along with its state.

:param queue_name
String with the queue name where to perform the query.
:return:
JSON data with the jobs allocated to the specified queue.

Parameters:

- `queue_name` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[GET] /v1/restricted-queues`

List all agent's restricted queues and its owners.

Returns:

JSON data matching the `RestrictedQueueOut` schema.

Status Codes:

- `HTTP 200 (OK)`

## `[POST] /v1/restricted-queues/<queue_name>`

Add an owner to the specific restricted queue.

Parameters:

- `queue_name` (string, path)

Request Body:

- `client_id` (string)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

## `[GET] /v1/restricted-queues/<queue_name>`

Get restricted queues for a specific agent.

Parameters:

- `queue_name` (string, path)

Returns:

JSON data matching the `RestrictedQueueOut` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[DELETE] /v1/restricted-queues/<queue_name>`

Delete an owner from the specific restricted queue.

Parameters:

- `queue_name` (string, path)

Request Body:

- `client_id` (string)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

## `[POST] /v1/result/<job_id>`

Post a result for a specified job_id.

:param job_id: UUID as a string for the job
:raises HTTPError: If the job_id is not a valid UUID

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

## `[GET] /v1/result/<job_id>`

Return results for a specified job_id.

:param job_id: UUID as a string for the job
:raises HTTPError: If the job_id is not a valid UUID

Parameters:

- `job_id` (string, path)

Returns:

JSON data matching the `ResultGet` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[POST] /v1/result/<job_id>/artifact`

Post artifact bundle for a specified job_id.

:param job_id:
UUID as a string for the job

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[GET] /v1/result/<job_id>/artifact`

Return artifact bundle for a specified job_id.

:param job_id:
UUID as a string for the job
:return:
send_file stream of artifact tarball to download

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[POST] /v1/result/<job_id>/log/<log_type>`

Post logs for a specified job ID.

:param job_id: UUID as a string for the job
:param log_type: LogType enum value for the type of log being posted
:raises HTTPError: If the job_id is not a valid UUID
:param json_data: Dictionary with log data

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
- `HTTP 404 (Not Found)`
- `HTTP 422 (Unprocessable Entity)`: Validation error

## `[GET] /v1/result/<job_id>/log/<log_type>`

Get logs for a specified job_id.

:param job_id: UUID as a string for the job
:param log_type: LogType enum value for the type of log requested
:raises HTTPError: If the job_id is not a valid UUID or if invalid query
:return: Dictionary with log data

Parameters:

- `job_id` (string, path)
- `log_type` (string, path)

Returns:

JSON data matching the `LogGet` schema.

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[POST] /v1/result/<job_id>/output`

Legacy endpoint to post output for a specified job_id.

TODO: Remove after CLI/agent migration completes.

:param job_id: UUID as a string for the job
:raises HTTPError: BAD_REQUEST when job_id is invalid
:return: "OK" on success

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[GET] /v1/result/<job_id>/output`

Legacy endpoint to get job output for a specified job_id.

TODO: Remove after CLI/agent migration completes.

:param job_id: UUID as a string for the job
:raises HTTPError: BAD_REQUEST when job_id is invalid
:return: Plain text output

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[POST] /v1/result/<job_id>/serial_output`

Legacy endpoint to post serial output for a specified job ID.

TODO: Remove after CLI/agent migration completes.

:param job_id: UUID as a string for the job
:raises HTTPError: BAD_REQUEST when job_id is invalid
:return: "OK" on success

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

## `[GET] /v1/result/<job_id>/serial_output`

Legacy endpoint to get latest serial output for a specified job ID.

TODO: Remove after CLI/agent migration completes.

:param job_id: UUID as a string for the job
:raises HTTPError: BAD_REQUEST when job_id is invalid
:return: Plain text serial output

Parameters:

- `job_id` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`

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

## `[DELETE] /v1/secrets/<client_id>/<path>`

Remove a secret value for the specified client_id and path.

Parameters:

- `client_id` (string, path)
- `path` (string, path)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 404 (Not Found)`
