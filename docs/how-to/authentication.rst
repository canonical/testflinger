Authentication using Testflinger CLI
====================================

:doc:`Authentication <../explanation/authentication>` is required for submitting jobs with priority, submitting jobs to a restricted queue, or reserving a machine for greater than 6 hours.

Authenticating with Testflinger server requires a client id and a secret key.
These credentials can be provided to the CLI using the environment variables
``TESTFLINGER_CLIENT_ID`` and ``TESTFLINGER_SECRET_KEY``. You can put these
variables in a .env file:

.. code-block:: shell

	TESTFLINGER_CLIENT_ID=my_client_id
	TESTFLINGER_SECRET_KEY=my_secret_key


You can then export these variables in your shell:

.. code-block:: shell

	set -a
	source .env
	set +a


With these variables set, you can ``testflinger_cli submit`` your jobs normally, and the authentication will be done by the CLI
automatically.

Alternatively, you can set the client id and secret key using
command line arguments:

.. code-block:: shell

	$ testflinger-cli submit example-job.yaml --client_id "my_client_id" --secret_key "my_secret_key"

However, this is not recommended for security purposes.
