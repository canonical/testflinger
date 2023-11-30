Connect to a different server
==============================

By default, Testflinger CLI uses the default Testflinger server located at ``https://testflinger.canonical.com``. To specify a different server to use, you can either run Testflinger CLI with the ``--server`` parameter, or set an environment variable.


Specify the server in command line
---------------------------------------

Run the Testflinger CLI command with an ``--server <SERVER>`` argument. The server URI must start with either ``http://`` or ``https://``. For example:

.. code-block:: shell

    $ testflinger-cli --server https://testflinger.example.com jobs

However, if the environment variable ``TESTFLINGER_SERVER`` is set, this argument will be ignored.


Set an environment variable
-----------------------------

If you want to use a server URI for all operations, you can set the environment variable ``TESTFLINGER_SERVER``. This variable overwrites the default server address and the string specified by the ``--server`` argument.

To set an environment variable on Ubuntu:

.. code-block:: shell

    $ export TESTFLINGER_SERVER="https://testflinger.example.com" 

If you want to change the environment variable permanently, add the export command to a system-wide or user-specific configuration file.

To verify that the variable has been set, run:

.. code-block:: shell

    $ printenv TESTFLINGER_SERVER
