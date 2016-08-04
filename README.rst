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

To create a virtual environment and install testflinger:

.. code-block:: console

  $ virtualenv env
  $ . env/bin/activate
  $ ./setup install

Testing
-------

To run the unit tests, first install (see above) then:

.. code-block:: console

  $ ./setup test

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

Configuration values can be loaded from a file. By default, testflinger will
look for testflinger.conf in the testflinger source directory. If you want
to change the location for the configuration file, set the environment variable
*TESTFLINGER_CONFIG* to the path of your configuration file.  If no config file
is found, defaults will be used.

Currently supported configuration values are:

- **DATA_PATH**: directory where result files will be stored

  - Default: ''/data'' under the testflinger module directory

- **REDIS_HOST**: host or ip of the redis server

  - Default: ''localhost''

- **REDIS_PORT**: port of the redis server

  - Default: ''6379''

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
