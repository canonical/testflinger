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

- **AMQP_URI**: URI to use for connecting to the rabbit Server

  - Default: ''amqp://guest:guest@localhost:5672//''

API
---

**[POST] /v1/job** - Create a test job request and place it on the specified queue

Most parameters passed in the data section of this API will be specific to the
type of agent receiving them. The *job_queue* parameter is used to designate
the rabbit queue used, but all others will be passed along to the agent.

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
