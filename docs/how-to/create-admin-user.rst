Create or edit Testflinger admin credentials
============================================

This document is intended for administrators and outlines the process for creating or editing a Testflinger admin account.

Create initial Testflinger admin credentials
--------------------------------------------

For tasks that require admin permissions through the CLI, a new `client_id` must be created to perform privileged actions.
By default, this `client_id` is ``testflinger-admin``, but its password must be set manually.

To set the initial password, log in to the Juju model where Testflinger is deployed and run the following command:

.. code-block:: shell

    juju run testflinger-k8s/leader set-admin-password password=<initial_password>

This will create an entry in the local database that can be used to perform privileged actions.
Refer to the :doc:`Authentication and Authorisation <authentication>` section for more details.

.. tip::

    ``testflinger-admin`` corresponds to the ``TESTFLINGER_CLIENT_ID``, while the password set using the Juju ``run`` command
    maps to the ``TESTFLINGER_SECRET_KEY`` environment variable.

Edit Testflinger admin credentials
----------------------------------

If password rotation is needed, the password for the ``testflinger-admin`` account can be updated by running the same Juju command:

.. code-block:: shell

    juju run testflinger-k8s/leader set-admin-password password=<new_password>

.. note::

    For more information on the Juju ``run`` command, please refer to the `Juju CLI`_ documentation.
