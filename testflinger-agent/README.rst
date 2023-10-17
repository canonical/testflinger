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

- **server_address**:

  - Host/IP and port of the testflinger server

- **execution_basedir**:

  - Base directory to use for running jobs (default: /tmp/testflinger/run)

- **logging_basedir**:

  - Base directory to use for agent logging (default: /tmp/testflinger/logs)

- **results_basedir**:

  - Base directory to use for temporary storage of test results to be transmitted to the server (default: /tmp/testflinger/results)

- **logging_level**:

  - Python loglevel name to use for logging (default: INFO)

- **logging_quiet**:

  - Only log to the logfile, and not to the console (default: False)

- **job_queues**:

  - List of queues that can be serviced by this device

- **advertised_queues**:

  - List of public queue names that should be reported to the server to report to users

- **advertised_images**:

  - List of images to associate with a queue name so that they can be referenced by name when using testflinger reserve

- **global_timeout**:

  - Maximum global timeout (in seconds) a job is allowed to specify for this device agent. The job will timeout during the provision or test phase if it takes longer than the requested global_timeout to run. (Default 4 hours)

- **output_timeout**:

  - Maximum output timeout (in seconds) a job is allowed to specify for this device agent. The job will timeout if there has been no output in the test phase for longer than the requested output_timeout. (Default 15 min.)

- **setup_command**:

  - Command to run for the setup phase

- **provision_command**:

  - Command to run for the provision phase

- **allocate_command**:

  - Command to run for the allocate phase

- **test_command**:

  - Command to run for the testing phase

- **reserve_command**:

  - Command to run for the reserve phase

- **cleanup_command**:

  - Command to run for the cleanup phase

Test Phases
-----------
The test will go through several phases depending on the configuration of the
test job and the configuration testflinger agent itself. If a <phase>_command
is not set in the testflinger-agent.conf (see above), then that phase will
be skipped. Even if the phase_command is configured, there are some phases
that are not mandatory, and will be skipped if the job does not contain data
for it, such as the provision, test, allocate, and reserve phases.

The following test phases are currently supported:

- **setup**:

  - This phase is run first, and is used to setup the environment for the
    test. The test job has no input for this phase and it is completely up to
    the device owner to include commands that may need to run here.

- **provision**:

  - This phase is run after the setup phase, and is used to provision the
    device by installing (if possible) the image requested in the test job.
    If the provision_data section is missing from the job, this phase will
    not run.

- **test**:
  
  - This phase is run after the provision phase, and is used to run the
    test_cmds defined in the test_data section of the job. If the test_data
    section is missing from the job, this will not run.

- **allocate**:

  - This phase is normally only used by multi-device jobs and is used to
    lock the agent into an allocated state to be externally controlled by
    another job. During this phase, it will gather device_ip information
    and push that information to the results data on the testflinger server
    under the running job's job_id.  Once that data is pushed successfully
    to the server, it will transition the job to a **allocated** state, which
    is just a signal that the parent job can make use of that data.  The
    **allocated** state is just a *job* state though, and not a phase that
    needs a separate command configured on the agent.
    Normally, the allocate_data section will be missing from the test job,
    and this phase will be skipped.

- **reserve**:
  
  - This phase is used for reserving a system for manual control.  This
    will push the requested ssh key specified in the job data to the
    device once it's provisioned and ready for use, then publish output
    to the polling log with information on how to reach the device over
    ssh.  If the reserve_data section is missing from the job, then this
    phase will be skipped.

- **cleanup**:
  
  - This phase is run after the reserve phase, and is used to cleanup the
    device after the test.  The test job has no input for this phase and
    it is completely up to the device owner to include commands
    that may need to run here.

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
