Manage client permissions
=========================

This document is intended for administrators and outlines the process to manage privileged users as
:doc:`authentication <../explanation/authentication>` is required for submitting jobs with priority, 
submitting jobs to a restricted queue, or reserving a machine for longer than 6 hours.

The following actions are supported to manage users with the admin CLI:

.. note::

   Using the admin CLI requires an account with admin privileges, 
   please refer to :doc:`Authentication and Authorisation <../how-to/authentication>`
   section for more information. 

List existing ``client_id`` 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can obtain a list with all existing ``client_id`` along with its permissions by using the ``get`` command

.. code-block:: shell

    testflinger-cli admin get client-permissions

You can also get the permissions for a single client_id:

.. code-block:: shell

    testflinger-cli admin get client-permissions --testflinger-client-id clientA

Create new ``client_id``
~~~~~~~~~~~~~~~~~~~~~~~~

You can create a new ``client_id`` by using individual arguments or by using ``json`` arguments. 

.. code-block:: shell

    testflinger-cli admin set client-permissions \
    --testflinger-client-id "clientA" --testflinger-client-secret "my-secret-password" \
    --max-priority '{"q1": 10}' --max-reservation '{}' --role "manager"

.. code-block:: shell

    testflinger-cli admin set client-permissions \
    --json '{"client_id": "clientA", "client_secret": "my-secret-password", "max_priority": {"q1": 10}, "max_reservation_time": {}}'

.. tip::

   If ``role`` is not provided either as argument or in JSON object, it will default to ``contributor``.
   
   Also, if ``max-priority`` and ``max-reservation`` are not provided, it will default to empty permissions: ``'{}'``

Update ``client_id``
~~~~~~~~~~~~~~~~~~~~

You can edit an existing ``client_id`` by using the ``update`` subcommand with only the necessary modifications. 

In the following examples, both max_priority and max_reservation are to be updated but providing single argument is also valid.
This can be useful for secret rotation (by specifying ``--testflinger-client-secret``) without modifying the other permissions.

.. code-block:: shell

    testflinger-cli admin update client-permissions \
    --testflinger-client-id "clientA" \
    --max-priority '{"q2": 10}' --max-reservation '{"q2": 43200}'

.. code-block:: shell

    testflinger-cli admin update client-permissions \
    --json '{"client_id": "clientA", "max_priority": {"q2": 10}, "max_reservation_time": {"q2": 43200}}'

.. tip::

   ``max_priority`` and ``max_reservation_time`` permissions are not additive, editing will replace existing values.
   To remove permissions, you can leave an empty value ``{}``.

Delete ``client_id``
~~~~~~~~~~~~~~~~~~~~

For deleting a ``client_id`` you can use the ``delete`` subcommand and specify the client to delete

.. code-block:: shell

    testflinger-cli admin delete client-permissions --testflinger-client-id clientA