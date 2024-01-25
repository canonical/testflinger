===========
Testflinger
===========

Overview
--------

Testflinger is a microservice that provides an API to request tests
and place the tests on a queue which can be serviced by any agent
capable of handling the test.

Installation
------------

Before installing testflinger, you will need to have a MongoDB server
available somewhere. The connection information for the database should be
configured using either environment variables or a testflinger.conf file
as described in the Configuration section.

To create a virtual environment and install testflinger, please run
the following commands in your testflinger directory:

.. code-block:: console

  $ virtualenv -p python3 env
  $ . env/bin/activate
  $ pip install .

Testing
-------

To run all the tests, install tox from packages or pypi and just run:

.. code-block:: console

  $ tox

Also, you can run just the unit tests directly by installing and running pytest

Usage
-----

After installing testflinger, you can run a test server locally with:

.. code-block:: console

  $ gunicorn testflinger:app

This will only allow connections from localhost by default. If you wish to
allow external connections, use the ''--bind'' option:

.. code-block:: console

  $ gunicorn --bind 0.0.0.0 testflinger:app

Configuration
-------------

Configuration values are read from environment variables.  If you prefer to
store the configuration in a config file, the config file should be sourced
prior to running the server so that the values may still be read from the
environment.

Currently supported configuration values are:

- **MONGODB_USERNAME**: Username for connecting to MongoDB

- **MONGODB_PASSWORD**: Password for connecting to MongoDB

- **MONGODB_DATABASE**: Name of the MongoDB database to use

- **MONGODB_AUTH_SOURCE**: Name of the database to use for authentication (Default: admin)

- **MONGODB_HOST**: host or ip of the MongoDB server

- **MONGODB_PORT**: MongoDB port to connect to (Default: 27017)

- **MONGODB_URI**: URI for connecting to MongoDB (used instead of the above config options)

  - Example: ''mongodb://user:pass@host:27017/dbname''

API
---

**[POST] /v1/job** - Create a test job request and place it on the specified queue

Most parameters passed in the data section of this API will be specific to the
type of agent receiving them. The *job_queue* parameter is used to designate
the queue used, but all others will be passed along to the agent.

- Parameters:

  - job_queue (JSON): queue name to use for processing the job

- Returns:

  {"job_id": <job_id> } (as JSON)

- Status Codes:

  - HTTP 200 (OK)

- Example:

  .. code-block:: console

    $ curl http://localhost:8000/v1/job -X POST \
         --header "Content-Type: application/json" \
         --data '{ "job_queue": "myqueue", "option":"foo" }'

**[GET] /v1/job** - Get a test job from the specified queue(s)

When an agent wants to request a job for processing, it can make this request
along with a list of one or more queues that it is configured to process. The
server will only return one job.

- Parameters:

  - queue (multivalue): queue name(s) that the agent can process

- Returns:

  JSON job data that was submitted by the requestor, or nothing if no jobs
  in the specified queue(s) are available.

- Status Codes:

  - HTTP 200 (OK)
  - HTTP 400 (Bad Request) - this is returned if no queue is specified
  - HTTP 204 (NO DATA)  - if there are no jobs in the specified queues

- Example:

  .. code-block:: console

    $ curl http://localhost:8000/v1/job?queue=foo\&queue=bar


** [GET] /v1/job/search ** - Search for jobs by tag(s) and state(s)

Parameters:

tags (array): List of string tags to search for
match (string): Match mode for tags - "all" or "any" (default "any")
state (array): List of job states to include (default all states other than cancelled and completed)
Returns:

Array of matching jobs

Example:

.. code-block:: console

$ curl 'http://localhost:8000/v1/job/search?tags=foo&tags=bar&match=all'

This will find jobs tagged with both "foo" and "bar".


**[POST] /v1/result/<job_id>** - post job outcome data for the specified job_id

- Parameters:

  - job_id: test job identifier as a UUID

- Status Codes:

  - HTTP 200 (OK)

- Example:

  .. code-block:: console

    $ curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000 \
         -X POST --header "Content-Type: application/json" \
         --data '{ "exit_code": 0, "output":"foo" }'

**[GET] /v1/result/<job_id>** - return previously submitted job outcome data

- Parameters:

  - job_id: test job identifier as a UUID

- Status Codes:

  - HTTP 200 (OK)
  - HTTP 204 (NO DATA) if there are no results for that ID yet

- Returns:

  JSON data previously submitted to this job_id via the POST API

- Example:

  .. code-block:: console

    $ curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000 \
         -X GET

**[POST] /v1/result/<job_id>/artifact** - upload a file artifact for the specified job_id

- Parameters:

  - job_id: test job identifier as a UUID

- Status Codes:

  - HTTP 200 (OK)

- Example:

  .. code-block:: console

    $ curl -X POST -F \
         "file=@README.rst" localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/artifact

**[GET] /v1/result/<job_id>/artifact** - download previously submitted artifact for this job

- Parameters:

  - job_id: test job identifier as a UUID

- Status Codes:

  - HTTP 200 (OK)
  - HTTP 204 (NO DATA) if there are no results for that ID yet

- Returns:

  JSON data previously submitted to this job_id via the POST API

- Example:

  .. code-block:: console

    $ curl http://localhost:8000/v1/result/00000000-0000-0000-0000-000000000000/artifact \
         -X GET -O artifact.tar.gz

**[POST] /v1/agents/queues** - post names/descriptions of queues serviced by this agent

- Status Codes:

  - HTTP 200 (OK)

- Example:

  .. code-block:: console

    $ curl http://localhost:8000/v1/agents/queues \
         -X POST --header "Content-Type: application/json" \
         --data '{ "myqueue": "queue 1", "myqueue2": "queue 2" }'

**[GET] /v1/agents/queues** - retrieve the list of well-known queues

- Status Codes:

  - HTTP 200 (OK)

- Returns:

  JSON data previously submitted by all agents via the POST API

- Example:

  .. code-block:: console

    $ curl http://localhost:8000/v1/agents/queues \
         -X GET

**[POST] /v1/agents/images** - post known images for the specified queue

- Status Codes:

  - HTTP 200 (OK)

- Example:

  .. code-block:: console

    $ curl http://localhost:8000/v1/agents/images \
         -X POST --header "Content-Type: application/json" \
         --data '{ "myqueue": { "image1": "url: http://place/imgae1" }}'

**[GET] /v1/agents/images/<queue>** - retrieve all known image names and the provisioning data used for them, for the specified queue

- Parameters:

  - queue: name of the queue to use

- Status Codes:

  - HTTP 200 (OK)

- Returns:

  JSON data previously submitted by all agents via the POST API

- Example:

  .. code-block:: console

    $ curl http://localhost:8000/v1/agents/images/myqueue \
         -X GET

**[POST] /v1/job/<job_id>/action** - execute action for the specified job_id

- Parameters:

  - job_id: test job identifier as a UUID

- Status Codes:

  - HTTP 200 (OK)
  - HTTP 400 (Bad Request) - the job is already completed or cancelled
  - HTTP 404 (Not Found) - the job isn't found
  - HTTP 422 (Unprocessable) - The action or the argument to it could not be processed

- Supported Actions:

  - Cancel - cancel a job that hasn't been completed yet

- Example:

  .. code-block:: console

    $ curl http://localhost:8000/v1/job/00000000-0000-0000-0000-000000000000/action \
         -X POST --header "Content-Type: application/json" \
         --data '{ "action":"cancel" }'

**[GET] /v1/agents/data** - retrieve all agent data

- Status Codes:

  - HTTP 200 (OK)

- Returns:

  JSON data for all known agents, useful for external systems that need to gather this information

- Example:

  .. code-block:: console

    $ curl -X GET http://localhost:8000/v1/agents/data
