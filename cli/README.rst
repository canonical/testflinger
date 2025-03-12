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

It is recommended that you install testflinger-cli from the snap, however it
can also be installed with pip directly from the source.

To install testflinger using the snap:

.. code-block:: console

  $ sudo snap install testflinger-cli

In order for Testflinger to see files/directories in removable media, you will
need to connect the ``removable-media`` interface manually:

.. code-block:: console

  $ sudo snap connect testflinger-cli:removable-media

When changes are made to the CLI, the snap is automatically built and uploaded
to the `edge` channel. Once sufficient testing has been performed, this snap
is also published to the `stable` channel. If you prefer to use the latest
code, then you can specify `edge` instead in the command above.

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

To specify Testflinger authentication parameters, like client_id
and secret_key, you can use '--client_id' and '--secret_key' respectively.
You can also specify these parameters as environment variables,
'TESTFLINGER_CLIENT_ID' and 'TESTFLINGER_SECRET_KEY'.

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
job is completed.
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

