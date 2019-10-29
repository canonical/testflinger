=================
Testflinger Agent
=================

Testflinger agent waits for job requests on a configured queue, then processes
them. The Testflinger Server submits those jobs, and once the job is complete,
the agent can submit outcome data with limited results back to the server.

Overview
--------

Testflinger-agent connects to the Testflinger microservice to request and
service requests for tests.

Installation
------------

To create a virtual environment and install testflinger-agent:

.. code-block:: console

  $ virtualenv env
  $ . env/bin/activate
  $ ./setup install

Testing
-------

To run the unit tests, first install (see above) then:

.. code-block:: console

  $ ./setup test

Configuration
-------------

Configuration is loaded from a yaml configuration file called
testflinger-agent.conf by default. You can specify a different file
to use for config data using the -c option.

The following configuration options are supported:

- **agent_id**:

  - Unique identifier for this agent

- **polling_interval**:

  - Time to sleep between polling for new tests (default: 10s)

- **server address**:

  - Host/IP and port of the testflinger server

- **execution_basedir**:

  - Base directory to use for running jobs (default: /tmp/testflinger/run)

- **logging_basedir**:

  - Base directory to use for agent logging (default: /tmp/testflinger/logs)

- **logging_level**:

  - Python loglevel name to use for logging (default: INFO)

- **logging_quiet**:

  - Only log to the logfile, and not to the console (default: False)

- **job_queues**:

  - List of queues that can be serviced by this device

- **advertised_queues**:

  - List of public queue names that should be reported to the server to report to users

- **setup_command**:

  - Command to run for the setup phase

- **provision_command**:

  - Command to run for the provision phase

- **test_command**:

  - Command to run for the testing phase

- **cleanup_command**:

  - Command to run for the cleanup phase

Usage
-----

When running testflinger, your output will be automatically accumulated
for each stage (setup, provision, test, cleanup) and sent to the testflinger
server, along with an exit status for each stage. If any stage encounters a
non-zero exit code, no further stages will be executed, but the outcome will
still be sent.

If you have additional artifacts that you would like to save along with
the output, you can create a 'artifacts' directory from your test command.
Any files in the artifacts directory under your test execution directory
will automatically be compressed (tar.gz) and sent to the testflinger server.
