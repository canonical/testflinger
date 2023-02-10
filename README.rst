===============
Testflinger CLI
===============

Overview
--------

The testflinger-cli tool is used for interacting with testflinger
server. It can be used for things like submitting jobs, checking 
the status of them, and getting results.

Installation
------------

You can either run testflinger-cli from a checkout of the code, or
install it like any other python project.

To run it from a checkout, please make sure to first install python3-click
and python3-requests

To install it in a virtual environment:

.. code-block:: console

  $ virtualenv -p python3 env
  $ . env/bin/activate
  $ pip install .


Usage
-----

After installing testflinger-cli, you can get help by just running
'testflinger-cli' on its own, or by using the '--help' parameter.

To specify a different server to use, you can use the '--server'
parameter, otherwise it will default to the one running on
http://testflinger.canonical.com
You may also set the environment variable 'TESTFLINGER_SERVER' to
the URI of your server, and it will prefer that over the default
or the string specified by --server.

To submit a new test job, first create a yaml or json file containing
the job definition. Then run:
.. code-block:: console

  $ testflinger-cli submit mytest.json

If successful, this will return the job_id of the test job you submitted.
You can check on the status of that job by running:
.. code-block:: console

  $ testflinger-cli status <job_id>

To watch the output from the job as it runs, you can use the 'poll'
subcommand. This will display output in 10s chunks and exit when the
job is complete.
.. code-block:: console

  $ testflinger-cli poll <job_id>

To get the full json results from the job when it is done running, you can
use the 'results' subcommand:
.. code-block:: console

  $ testflinger-cli results <job_id>

Finally, to download the artifact tarball from the job, you can use the
'artifact' subcommand:
.. code-block:: console

  $ testflinger-cli artifact [--filename <DEFAULT:artifact.tgz>] <job_id>

