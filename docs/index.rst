:relatedlinks: [Project&#32;repository](https://github.com/canonical/testflinger)

.. _home:

Testflinger
============

Testflinger is a system for orchestrating time-shared access to a pool of
target machines.

Each Testflinger system consists of:

* a web service (called just Testflinger) that provides an API to request jobs
  by placing them on a queue
* per-machine agents that wait for jobs to be placed on queues they can service
  and then process them

Jobs can be either fully automated scripts that can attempt to complete within
the allocated time or interactive shell sessions.

The Testflinger system is particularly useful for sharing finite machine resources
between different consumers in a predictable fashion.

Typically this has been used for managing a test lab where CI/CD test runs and
also exploratory testing by human operators is desired.

---------

In this documentation
---------------------

The documentation is grouped into two domains of concern that mirror how
Testflinger is used: the **client side** (submitting and monitoring test jobs)
and the **server side** (deploying and operating a Testflinger lab).

Client side
~~~~~~~~~~~

For users who submit and monitor test jobs through the Testflinger CLI.

**Get started**
   :doc:`Install the CLI </how-to/install-cli>` •
   :doc:`Change the server </how-to/change-server>` •
   :doc:`Get started with the CLI </tutorial/index>`

**Work with jobs**
   :doc:`Submit a job </how-to/submit-job>` •
   :doc:`Retrieve logs </how-to/retrieve-logs>` •
   :doc:`Check job status </how-to/search-job>` •
   :doc:`Cancel a job </how-to/cancel-job>` •
   :doc:`Reserve a machine </how-to/reserve-job>` •
   :doc:`Set job priority </how-to/job-priority>`

**Define jobs**
   :doc:`Job schema </reference/job-schema>` •
   :ref:`Test phases <provision>` •
   :doc:`Device connector types </reference/device-connector-types>` •
   :doc:`CLI configuration </reference/cli-config>`

**Authenticate and protect secrets**
   :doc:`Authenticate with the server </how-to/authentication>` •
   :doc:`Use secrets </how-to/use-secrets>` •
   :doc:`Manage client permissions </how-to/manage-client-permissions>` •
   :ref:`Authentication and authorisation <authentication>`

Server side
~~~~~~~~~~~

For operators who deploy and maintain a Testflinger server, agent hosts, and
device connectors.

**Understand the system**
   :ref:`Architecture <architecture>` •
   :ref:`Agents <explain_agents>` •
   :ref:`Queues <queues>` •
   :ref:`Restricted queues <restricted-queues>` •
   :ref:`Extended reservation <extended-reservation>`

**Deploy and maintain the server**
   :ref:`Deploy the server <howto-deploy-server>` •
   :ref:`Maintain the server <howto-maintain-server>` •
   :doc:`Create an admin user </how-to/create-admin-user>`

**Deploy and maintain agent hosts**
   :doc:`Deploy an agent host </how-to/administer-agent-hosts/deploy-testflinger-agent-host>` •
   :ref:`Maintain an agent host <howto-manage-agent-host>` •
   :ref:`Manage agents <howto-manage-agent>` •
   :doc:`List agents </how-to/list-agents>`

**Configure components**
   :doc:`Server configuration </reference/testflinger-server-conf>` •
   :doc:`Agent configuration </reference/testflinger-agent-conf>` •
   :doc:`Device connector configuration </reference/device-connector-conf>` •
   :doc:`MAAS storage </reference/maas_storage>`

**Control access and secure the deployment**
   :doc:`API roles </reference/api-roles>` •
   :doc:`OpenAPI reference </reference/openapi>` •
   :ref:`Security overview <security_overview>` •
   :ref:`Secrets <secrets>`

---------

How this documentation is organised
-----------------------------------

This documentation follows the `Diátaxis <https://diataxis.fr/>`_ framework,
which divides content by the reader's needs. The
:doc:`Tutorial </tutorial/index>` takes you step-by-step through your first
test job. The :doc:`How-to guides </how-to/index>` assume basic familiarity and
cover key operations and common tasks. The
:doc:`Reference </reference/index>` provides technical details on schemas,
configuration, and APIs. The :doc:`Explanation </explanation/index>` offers
background and discussion of key concepts. The *In this documentation* map
above cuts across these tiers by domain of concern, so you can follow either
your task (Diátaxis) or your component (client or server).

---------

Project and community
---------------------

Testflinger is a member of the Ubuntu family. It is an open source project that
warmly welcomes community contributions, suggestions, fixes and
constructive feedback.

* This project follows the `Ubuntu Code of Conduct`_
* This project is `hosted on GitHub <canonical/testflinger_>`_ - contributions are welcome
* This project is governed by the Ubuntu `Security reporting and disclosure policy`_ 
* :ref:`Interested in using Testflinger for your project? Get in touch! <home>`


.. toctree::
   :hidden:
   :maxdepth: 2

   tutorial/index
   how-to/index
   reference/index
   explanation/index
