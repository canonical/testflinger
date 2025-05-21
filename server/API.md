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

## `[GET] /v1/job/queues/<queue_name>`

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
curl 'http://localhost:8000/v1/job/queues/foo'
```

This will find jobs in the queue `foo` and return its IDs, creation time and state. 

## `[POST] /v1/result/<job_id>`

Post job outcome data for the specified job_id

Parameters:

- `job_id` (UUID): test job identifier

Status Codes:

- `HTTP 200 (OK)`

Example:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000 \
  -X POST --header "Content-Type: application/json" \
  --data '{ "exit_code": 0, "output":"foo" }'
```

## `[GET] /v1/result/<job_id>`

Return previously submitted job outcome data

Parameters:

- `job_id` (UUID): test job identifier

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 204 (NO DATA)`: if there are no results for that ID yet

Returns:

JSON data previously submitted to this `job_id` via the POST API

Example:

```shell
curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000 -X GET
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

Authenticate client key and return JWT with permissions

Headers:

- Basic Authorization: client_id:client_key (Base64 Encoded)

Status Codes:

- `HTTP 200 (OK)`
- `HTTP 401 (Unauthorized)`: Invalid client_id or client-key

Returns:

Signed JWT with permissions for client

Example:

```shell
curl http://localhost:8000/v1/oauth2/token \
  -X GET --header "Authorization: Basic ABCDEF12345"
```
