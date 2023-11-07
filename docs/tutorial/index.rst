Get started with Testflinger CLI
=================================

Testflinger is a system for orchestrating the time-sharing of access to a pool of target machines. You can use Testflinger to perform remote real-world test jobs on hardware with optimised utilisation of resources.

Each Testflinger system consists of:

* **Testflinger Server**: a microservice that provides APIs and Web UI for dispatching your test jobs in the appropriate queues.
* **Testflinger Agent**: a per-machine management tool that retrieves jobs from associated queues on the server and processes the jobs.
* **Device Connector**: a device-specific tool that handles provisioning and other device-specific details for each type of device.

The **Testflinger CLI** is a command-line interface that facilitates interactions with a Testflinger Server through integrated APIs. You can use Testflinger CLI to submit test jobs, check job status, and retrieve testing results. 

In this tutorial, you will learn how to set up Testflinger CLI, write your first test job, and leverage the CLI to run the test job on a remote Testflinger server. 


Prerequisite
--------------

- Python installed on your system
- Access to a Testflinger server and a device under test (DUT)


Install Testflinger CLI
--------------------------

The most convenient way to install the CLI is through the *Snap Store*. Open a terminal and run the following command:

.. code-block:: shell
  
  $ sudo snap install testflinger-cli

Once the installation is finished, you can execute the ``testflinger-cli`` command to check the installation. For example, you can run with the ``--help`` or ``-h`` option to display the CLI help page, which is useful anytime when you need a reference about how to use the tool:

.. code-block::

  $ testflinger-cli --help

  usage: testflinger-cli [-h] [-c CONFIGFILE] [-d] [--server SERVER]
                        {artifacts,cancel,config,jobs,list-queues,poll,reserve,results,show,status,submit}
                        ...

  positional arguments:
    {artifacts,cancel,config,jobs,list-queues,poll,reserve,results,show,status,submit}
      artifacts           Download a tarball of artifacts saved for a specified job
      cancel              Tell the server to cancel a specified JOB_ID
      config              Get or set configuration options
      jobs                List the previously started test jobs
      list-queues         List the advertised queues on the Testflinger server
      poll                Poll for output from a job until it is completed
      reserve             Install and reserve a system
      results             Get results JSON for a completed JOB_ID
      show                Show the requested job JSON for a specified JOB_ID
      status              Show the status of a specified JOB_ID
      submit              Submit a new test job to the server

  optional arguments:
    -h, --help            show this help message and exit
    -c CONFIGFILE, --configfile CONFIGFILE
                          Configuration file to use
    -d, --debug           Enable debug logging
    --server SERVER       Testflinger server to use


Congratulations, your Testflinger CLI is ready for use!

.. note::
  
  ``testflinger`` and ``testflinger-cli`` are aliases for the same command. You can use both commands interchangeably.


Configure default server
----------------------------

The default server for Testflinger CLI to use is ``https://testflinger.canonical.com``. Let's assume that you want to connect to another server located in your own hardware laboratory, with the new URI ``https://testflinger.example.com``. We will use this example server URI throughout this tutorial.

To change the default server to connect, set the server URI as an environment variable. In the terminal, run the following command:

.. code-block:: shell
  
  $ export TESTFLINGER_SERVER="https://testflinger.example.com"

To verify that the variable has been set, run:

.. code-block:: shell

  $ printenv TESTFLINGER_SERVER
  https://testflinger.example.com

Now all the Testflinger requests made from your current terminal session will be directed to the new server.

Access to a Testflinger server is usually secured behind a firewall or with additional authentication and authorisation measures. Make sure that you have been granted the right access through your system administrator.

Check available queues on the server
-------------------------------------

You can now use the CLI to connect to a Testflinger server and check the availability of remote resources.

Before submitting a test job, you need to identify the appropriate job queue to use on the server. Queues are usually dedicated to one type of device.

Run the following command in the terminal to retrieve the available job queues to use:

.. code-block:: shell

  $ testflinger-cli list-queues

.. note::
  
  If you want to temporarily use another server, add ``--server`` argument and the server URI in the command.

If the connection is successful, a list of job queues is returned with their queue names and short descriptions:

.. code-block::

  Advertised queues on this server:
    example-queue-1 - for testing device model-1
    example-queue-2 - for testing device model-2
    example-queue-3 - for testing device model-3
    ...

In this tutorial, let's assume that the job queue you will use is ``example-queue-1``.

Alternatively, you can also visit the Web UI of this server at ``https://testflinger.example.com``, where the list of agents, queues and jobs are displayed.


Define a test job
--------------------

Test jobs are YAML or JSON files that define the configurations and instructions about how the test should run on the target device. Test jobs can be either fully automated scripts or interactive shell sessions.

A test job might contain a very complex command workflow that includes provisioning a system image onto the device, updating the firmware, executing a series test and more. In this tutorial, you will start with a simple test job.

The following example shows a test job, written in YAML, that provisions an Ubuntu Jammy system image on the target device and then prints the distribution information:

.. code-block:: yaml

  job_queue: example-queue-1
  provision_data:
    url: https://cdimage.ubuntu.com/ubuntu/releases/jammy/release/example.img.xz
  test_data:
    test_cmds: |
      ssh -t ubuntu@DEVICE_IP lsb_release -a

In the example job definition file:

- ``job_queue``: specifies the queue name to which you will submit the job 
- ``provision_data``: specifies the source of the system image to be provisioned on the target device. This example uses a URL of the system image to be downloaded, but the actual format of this section varies on device type.
- ``test_data``: contains a ``test_cmds`` section that specifies the list of commands to be executed on the device after the system is provisioned. In this example, the device is instructed to execute the ``lsb_release -a`` command to print the Linux distribution information. 

You might have noticed that the command is executed over an SSH connection. This is because the Testflinger system uses agents and device connectors to manage test jobs. The test commands are not executed on the test device itself, but on a host system that can reach your test device via SSH. Devices are set up with an SSH key to allow passwordless SSH connection from the test host at the time the provisioning is finished. 

Modify the strings in the above example as needed, and then save the file on your disk. For example, you can name it as ``test-job.yaml``.

Submit your test job
---------------------

Now that you have a YAML file with your job definition, you can submit it to the Testflinger server by executing the following command:

.. code-block:: shell

  $ testflinger-cli submit test-job.yaml

Testflinger CLI submits the job to the specified Testflinger server, which will then dispatch the job to the agent associated with the job queue. The agent receives the job, processes the job definition file and passes the job data to the device connector. Data specified for provisioning and testing will be executed by the device connector.

If the job is submitted successfully, you will see the output with a returned ``job_id`` in the form of UUID. You will use this ID for later operations.

.. code-block:: shell

  Job submitted successfully!
  job_id: 2bac1457-0000-0000-0000-15f23f69fd39

Check job status
-----------------------

Once the job is submitted to the server, it goes through a series of phases in the lifecycle. You might want to check its status during the processing time. To do so, run the following command with the actual ``job_id`` of your submitted job:

.. code-block:: shell

  $ testflinger status 2bac1457-0000-0000-0000-15f23f69fd39

  provision

This command provides you with brief information about the job's current status, including whether it is running, completed, or has been cancelled.

The above output implies that the test job is going through the provisioning phase. If the job is completed, the returned status shows ``complete``.

Check test output
------------------------

In some cases, you might want to check the device output to know how each job phase runs. You can use Testflinger CLI to collect the job output in a JSON file by running the ``results`` command with the actual ``job_id`` of your submitted job:

.. code-block:: shell

  $ testflinger results 2bac1457-0000-0000-0000-15f23f69fd39

  {
    "cleanup_output": "Starting testflinger cleanup phase on example-queue-1\n",
    "cleanup_status": 0,
    "job_state": "complete",

    "provision_output": "Starting testflinger provision phase on example-queue-1\n...",     
    "provision_serial": "...",
    "provision_status": 0,

    "setup_output": "Starting testflinger setup phase on example-queue-1\n",
    "setup_status": 0,

    "test_output": "Starting testflinger test phase on example-queue-1\n...",
    "test_serial": "...",
    "test_status": 0
  }

Besides the output from the provisioning and testing commands, the returned data also includes an exit code of each phase and output from the Testflinger agent. This information is very useful for troubleshooting testing issues.

---------

Congratulations! You've successfully set up the Testflinger CLI, created and submitted your first test job, and checked its status. You can now create more complex jobs and manage your test jobs efficiently using the command line tool. Happy testing!

Next steps
--------------

Now that you've mastered the basic operations you can do with Testflinger CLI, here are some next steps to enhance your experience:

- Check the :doc:`Testflinger How-to guides <../how-to/index>`
- Check the :doc:`Testflinger Reference docs <../reference/index>`
- Learn about the :doc:`key concepts of Testflinger <../explanation/index>`

If you encounter any issues, we are here to help you. Please let us know - `Ubuntu Discourse`_.
