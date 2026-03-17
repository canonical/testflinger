Use Secrets
===========

Testflinger allows you to securely store and manage secrets for later use in your jobs.
This how-to guide explains the lifecycle of secrets in Testflinger and how to use them 
in your job definitions.

For more information on how secrets work in Testflinger, please refer to the 
:doc:`Testflinger Secrets explanation <../explanation/secrets>`.

For information on the overall secret structure, please refer to the 
:doc:`Secrets reference <../reference/secrets>`.

Prerequisites
-------------

Authentication is required to create, use and delete secrets. The following instructions 
assumes that you have already authenticated with the Testflinger server. If you haven't 
authenticated yet, please refer to the :doc:`Authentication using Testflinger CLI <authentication>` 
guide.

Create a Secret
---------------

To create a secret, you will need to define a path where you would like to store the 
secret and the value of the secret. This path is located under a dedicated namespace
that is automatically determined by the authenticated Testflinger ``client-id``.

.. code-block:: shell

    testflinger-cli secret write path/to/secret 'my_secret_value'

.. tip::
    To update the secret value, you can simply run the same command again with the new value. 

Use a Secret in a job
---------------------

Jobs can reference secrets stored in Testflinger by using the ``secrets`` field in the job definition.

.. note::
    The ``secrets`` field is only supported in the ``test_data`` section of a job.

.. code-block:: yaml

    job_queue: <queue>
    test_data:
      secrets:
        SUPERSECRET: path/to/secret
      test_cmds: |
        echo "The secret is $SUPERSECRET"

In the above example, the job references a secret stored at the path ``path/to/secret`` and makes it
available as an environment variable named ``SUPERSECRET`` during the execution of the test commands.

Furthermore, in this example, the echoed value would not be exposed in the logs because of 
:ref:`secret Masking <secrets-masking>`.

.. note::
    During job submission, secrets are available only to the authenticated user with the Testflinger 
    ``client-id`` that created them. If a secret needs to be shared among multiple users, contact the 
    Testflinger administrator and request a team-shared ``client-id``.

Delete a Secret
---------------

To delete a secret, you can use the following command:

.. code-block:: shell

    testflinger-cli secret delete path/to/secret