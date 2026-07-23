Authenticate using Testflinger CLI
==================================

:doc:`Authentication <../explanation/authentication>` is required for submitting
jobs with priority or to a restricted queue, reserving a machine for longer than
6 hours, or using :doc:`secrets <../explanation/secrets>`.
Additionally, if the Testflinger server is configured with an OpenID Connect
(OIDC) provider, authentication is required for any request made to the server.

.. note::

   Changing an agent status also requires authentication and is limited to
   admin users only. For more information, refer to
   :doc:`Testflinger Agents <../explanation/agents>`.

With credentials
----------------

Testflinger supports basic authentication using a ``client_id`` and a ``secret_key``.
These credentials are provided by the Testflinger server administrator and can
be used either by setting environment variables or by passing them as command line
arguments.

For the following example, we'll start by creating a ``.env`` file with the
following environment variables:

.. code-block:: shell

	TESTFLINGER_CLIENT_ID='my_client_id'
	TESTFLINGER_SECRET_KEY='my_secret_key'


You can then export these variables in your shell:

.. code-block:: shell

	set -a
	source .env
	set +a


With these variables set, the CLI will automatically handle all authentication,
so you can run any command such as ``testflinger-cli submit`` without needing
to provide the credentials explicitly.

Alternatively, you can set the ``client_id`` and ``secret_key`` using
command line arguments, however, this is not recommended for security purposes.

.. code-block:: shell

	$ testflinger-cli submit example-job.yaml --client_id 'my_client_id' --secret_key 'my_secret_key'

.. tip::

   If you are using the CLI snap, run ``testflinger-cli login`` after setting
   your environment variables (or with the credentials as command line arguments)
   to store a refresh token in a snap-local cache. The token persists across
   terminal sessions and is valid for 6 days, so you will not need to supply
   credentials again until it expires.

With OpenID Connect (OIDC)
--------------------------

If the Testflinger server is configured with an OpenID Connect (OIDC) provider,
you can authenticate using your OIDC credentials. The CLI will prompt you to log
in through your web browser, and upon successful authentication, it will store a
refresh token that can be used for future requests.

To authenticate with OIDC, run:

.. code-block:: shell

	$ testflinger-cli login
	Please visit https://login.example.com/oauth2/device/verify and enter code 123456 to log in.

The CLI will display a URL and a code. If your browser does not open automatically,
you can manually visit the provided URL and enter the code displayed in the terminal.

Once you enter the code and log in successfully, the CLI may take a few seconds to complete the
authentication process and display a success message.

.. code-block:: shell

	$ testflinger-cli login
	Please visit https://login.example.com/oauth2/device/verify and enter code 123456 to log in.
	Successfully authenticated as 'user@example.com'

.. note::
   
   The CLI will poll in the background for the authentication to complete. 
   Keep in mind that if you close the terminal or if you don't complete the
   login process within a certain time frame (usually a few minutes), the
   authentication will fail and you'll need to run the command again.

Upon successful authentication, the CLI will store a refresh token in a snap-local
cache that can be used for any additional CLI command. The token is valid for 6 days, 
after which you will need to re-authenticate.
