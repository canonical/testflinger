Retrieve job logs
=================

When a Testflinger job runs, the agent captures output from each test phase and streams it to the server as log fragments. You can retrieve these logs using the CLI or API.

Using the CLI
-------------

The Testflinger CLI provides commands to retrieve both standard output and serial console logs for your jobs.

Get standard output
~~~~~~~~~~~~~~~~~~~

To retrieve the standard output from all phases of a job:

.. code-block:: shell

  $ testflinger-cli results <job_id>

This will display the combined output from all test phases (setup, provision, test, etc.) that were executed.

Monitor logs in real-time
~~~~~~~~~~~~~~~~~~~~~~~~~~

You can poll for job output and see logs as they become available:

.. code-block:: shell

  $ testflinger-cli poll <job_id>

This command will:

1. Wait for the job to start execution
2. Display output as it's generated
3. Continue until the job completes
4. Return an exit code matching the job's outcome

For serial console output:

.. code-block:: shell

  $ testflinger-cli poll-serial <job_id>

Advanced polling options
~~~~~~~~~~~~~~~~~~~~~~~~~

The ``poll`` and ``poll-serial`` commands support several options for more control:

**Filter by test phase**

Retrieve logs from only a specific test phase:

.. code-block:: shell

  # Get only provision phase logs
  $ testflinger-cli poll --phase provision <job_id>

  # Get only test phase serial logs
  $ testflinger-cli poll-serial --phase test <job_id>

Available phases: ``setup``, ``provision``, ``firmware_update``, ``test``, ``allocate``, ``reserve``, ``cleanup``

**Start from a specific fragment**

When monitoring long-running jobs, you can retrieve only new logs by specifying a starting fragment number:

.. code-block:: shell

  # Start from fragment 10 onwards
  $ testflinger-cli poll --start_fragment 10 <job_id>

  # Or using short option
  $ testflinger-cli poll -f 10 <job_id>

This is useful when you've already retrieved earlier logs and only want new output.

**Filter by timestamp**

Retrieve only logs created after a specific time:

.. code-block:: shell

  # Get logs after a specific timestamp (ISO 8601 format)
  $ testflinger-cli poll --start_timestamp "2025-10-15T10:30:00" <job_id>

  # Or using short option
  $ testflinger-cli poll -t "2025-10-15T10:30:00" <job_id>

**Combine multiple filters**

You can combine phase, fragment, and timestamp filters:

.. code-block:: shell

  # Get test phase logs from fragment 5 onwards
  $ testflinger-cli poll --phase test --start_fragment 5 <job_id>

  # Get provision logs after a specific timestamp
  $ testflinger-cli poll --phase provision --start_timestamp "2025-10-15T10:00:00" <job_id>

**One-shot mode**

To get the latest output without continuous polling:

.. code-block:: shell

  # Get latest standard output and exit
  $ testflinger-cli poll --oneshot <job_id>

  # Get latest serial output and exit
  $ testflinger-cli poll-serial --oneshot <job_id>

  # Get latest output with options
  $ testflinger-cli poll --oneshot --phase test --start_fragment 10 <job_id>

**JSON output mode**

Get structured JSON output instead of plain text:

.. code-block:: shell

  # Get logs in JSON format
  $ testflinger-cli poll --json <job_id>

The JSON output includes:

.. code-block:: json

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

Using the API directly
----------------------

For advanced use cases, you can query the logging API directly to access specific phases, time ranges, or log fragments.

Get all logs for a job
~~~~~~~~~~~~~~~~~~~~~~~

To retrieve all standard output logs:

.. code-block:: shell

  curl http://testflinger.example.com/v1/result/<job_id>/log/output

To retrieve all serial console logs:

.. code-block:: shell

  curl http://testflinger.example.com/v1/result/<job_id>/log/serial

Filter logs by test phase
~~~~~~~~~~~~~~~~~~~~~~~~~~

To retrieve logs from only a specific test phase:

.. code-block:: shell

  # Get only setup phase logs
  curl "http://testflinger.example.com/v1/result/<job_id>/log/output?phase=setup"

  # Get only provision phase logs
  curl "http://testflinger.example.com/v1/result/<job_id>/log/output?phase=provision"

Retrieve incremental log updates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For long-running jobs, you can retrieve only new log data by specifying a starting fragment number:

.. code-block:: shell

  # Get logs from fragment 10 onwards
  curl "http://testflinger.example.com/v1/result/<job_id>/log/output?start_fragment=10"

Query logs by timestamp
~~~~~~~~~~~~~~~~~~~~~~~

You can filter logs to only retrieve entries created after a specific time:

.. code-block:: shell

  curl "http://testflinger.example.com/v1/result/<job_id>/log/output?start_timestamp=2025-10-15T10:30:00Z"

Combine multiple filters
~~~~~~~~~~~~~~~~~~~~~~~~~

You can combine phase, fragment, and timestamp filters:

.. code-block:: shell

  # Get test phase logs from fragment 5 onwards
  curl "http://testflinger.example.com/v1/result/<job_id>/log/output?phase=test&start_fragment=5"

  # Get provision logs after a specific timestamp
  curl "http://testflinger.example.com/v1/result/<job_id>/log/output?phase=provision&start_timestamp=2025-10-15T10:00:00Z"

Understanding the log structure
--------------------------------

Testflinger captures two types of logs:

Standard output (``output``)
  Contains the console output from commands executed during each test phase. This includes:

  - Setup commands
  - Provisioning output from device connectors
  - Test command output
  - Cleanup operations

Serial console logs (``serial``)
  Contains output from the device's serial console during provisioning and testing. This is particularly useful for:

  - Debugging boot issues
  - Viewing kernel messages
  - Monitoring low-level device behavior
  - Troubleshooting hardware problems

Log characteristics
~~~~~~~~~~~~~~~~~~~

Both log types are:

- **Persistent**: Logs are stored on the server and can be retrieved multiple times (unlike the old system where logs were deleted on retrieval)
- **Phase-organized**: Each test phase has separate logs for easier debugging
- **Timestamped**: Every log fragment includes a timestamp for precise time-based queries
- **Fragmented**: Large logs are automatically split into manageable chunks for efficient streaming
- **Queryable**: You can filter by phase, fragment number, or timestamp

Log fragments
~~~~~~~~~~~~~

The logging system breaks logs into fragments:

- Each fragment is numbered sequentially starting from 0
- Fragments are created as output is generated in real-time
- ``last_fragment_number`` in the response indicates the highest fragment available
- Use ``start_fragment`` to retrieve only new fragments since your last query

Example: Monitoring a long-running job
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's how you might monitor a long-running job from the command line:

.. code-block:: shell

  # Initial check - get all logs so far
  testflinger-cli poll --oneshot --json my-job-id > initial.json

  # Extract the last fragment number (requires jq)
  LAST_FRAG=$(jq '.output | to_entries | map(.value.last_fragment_number) | max' initial.json)

  # Wait a while, then get only new logs
  sleep 60
  testflinger-cli poll --oneshot --start_fragment $((LAST_FRAG + 1)) my-job-id

  # Or continuously poll with automatic fragment tracking
  testflinger-cli poll my-job-id

The ``poll`` command automatically tracks fragments for you, so you don't need to manually manage fragment numbers during continuous monitoring.

Backward compatibility
----------------------

The existing CLI commands continue to work as before. The server automatically reconstructs the traditional log format from the new fragment-based storage system.

Legacy behavior:
  - ``testflinger-cli results <job_id>`` - Returns combined results with logs
  - ``testflinger-cli poll <job_id>`` - Polls for output (now with optional filters)
  - ``testflinger-cli poll-serial <job_id>`` - Polls for serial output (now with optional filters)

New features are opt-in through command-line flags, so existing scripts and workflows remain unaffected.

See also
--------

- :doc:`submit-job` - How to submit jobs
- :doc:`../reference/test-phases` - Understanding test phases
- :doc:`../reference/logging-architecture` - Technical details of the logging system
