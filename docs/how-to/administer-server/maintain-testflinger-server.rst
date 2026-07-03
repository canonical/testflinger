.. _howto-maintain-server:

Maintain a Testflinger Server
=============================

This guide outlines how to maintain a Testflinger server deployed with
Juju. To deploy a Testflinger server, please read the
:doc:`deploy-testflinger-server` guide.

Refresh Testflinger Server
--------------------------

For updating the Testflinger server or charm code, you will need to
refresh the charm.

.. code-block:: shell

  $ juju refresh testflinger-k8s

.. tip::

  You can optionally use the ``--channel`` flag to specify a different
  channel to refresh from.

Enable Testflinger Secrets
--------------------------

Testflinger server can be configured to allow using secrets to store
sensitive information in job definitions. To enable this feature, you
will need to configure a secret store backend. The following steps
specify how to enable secrets, for detailed information on Testflinger
secrets, please refer to :doc:`../../explanation/secrets`.

MongoDB Client-Side Field Level Encryption
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To enable MongoDB Client-Side Field Level Encryption (CSFLE) for
secrets, you will need to configure the Testflinger server to use the
existing MongoDB charm deployment as the secret store backend.

.. code-block:: shell

  $ juju integrate testflinger-k8s:mongodb_keyvault mongodb:database
  $ juju config testflinger-k8s \
      testflinger_secrets_master_key="<master-key>"

The above command will automatically create a new database in the MongoDB charm
deployment, and allow Testflinger to connect to it. This database will be used
by Testflinger to store the encryption keys which can later be used to decrypt
secrets so that they can be accessed by agents at job runtime.

.. note::

  The ``testflinger_secrets_master_key`` is used to encrypt the CSFLE data keys
  stored in MongoDB. Generate a secure random base64-encoded string by running
  the following command: ``openssl rand -base64 96 | tr -d '\n'``
