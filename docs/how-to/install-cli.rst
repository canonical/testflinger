Install Testflinger CLI
========================

The ``testflinger-cli`` client is a command line tool used for interacting with Testflinger servers. You can use the client to submit test jobs to the devices under test (DUT), check the job status and get testing results.

You can either install ``testflinger-cli`` through Snap or check out the code from our GitHub repository and run the tool in a Python virtual environment.


Install via Snap
-----------------
The most convenient way to get the CLI tool is via snap:

.. code-block:: shell

    $ sudo snap install testflinger-cli


Install in virtual environment
-------------------------------

If you are using the CLI from an automated test runner, such as Jenkins, you may want to install the tool in a virtual environment instead.

To run it from the source code, please make sure that the ``python3-click`` and ``python3-requests`` packages are installed, and then run the following commands:

.. code-block:: shell

  $ git clone https://github.com/canonical/testflinger
  $ cd cli
  $ virtualenv -p python3 env
  $ . env/bin/activate
  $ pip install .


