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

Get started
~~~~~~~~~~~

Install the client, run your first job, and learn the core workflow.

* **First steps**: :doc:`Get started with Testflinger <tutorial/index>` • :doc:`Install the CLI <how-to/install-cli>` • :doc:`Change server <how-to/change-server>`

Submit and manage jobs
~~~~~~~~~~~~~~~~~~~~~~~

The day-to-day workflow for creating test jobs, submitting them, and collecting results.

* **Set up access**: :doc:`Authenticate with the server <how-to/authentication>`
* **Run jobs**: :doc:`Submit <how-to/submit-job>` • :doc:`Cancel <how-to/cancel-job>` • :doc:`Search <how-to/search-job>` • :doc:`Retrieve results <how-to/retrieve-logs>` • :doc:`Use secrets <how-to/use-secrets>`
* **Reserve and prioritize**: :doc:`Reserve a machine <how-to/reserve-job>` • :doc:`Set job priority <how-to/job-priority>` • :doc:`Queues <explanation/queues>` • :doc:`Restricted queues <explanation/restricted-queues>`
* **Job definitions**: :doc:`Job schema <reference/job-schema>` • :doc:`Test phases <reference/test-phases>` • :doc:`CLI configuration <reference/cli-config>`

Administer Testflinger server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For server administrators running the central Testflinger web service - a Kubernetes
application deployed with Juju, backed by MongoDB.

* **Deploy and maintain server**: :doc:`Deploy <how-to/administer-server/deploy-testflinger-server>` • :doc:`Maintain <how-to/administer-server/maintain-testflinger-server>` • :doc:`Configuration <reference/testflinger-server-conf>` • :doc:`Architecture <explanation/architecture>`
* **Users and access**: :doc:`Create an admin user <how-to/create-admin-user>` • :doc:`Manage client permissions <how-to/manage-client-permissions>` •  :doc:`Configure OIDC auth <reference/juju-oidc-config>` • :doc:`API roles <reference/api-roles>`
* **REST API**: :doc:`API reference (OpenAPI) <reference/openapi>`

Administer agent hosts and devices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For lab administrators running the machines that execute jobs - agent hosts deployed
with Juju, each running agents connected to physical machines under test.

* **Deploy and maintain agent hosts**: :doc:`Deploy an agent host <how-to/administer-agent-hosts/deploy-testflinger-agent-host>` • :doc:`Maintain an agent host <how-to/administer-agent-hosts/maintain-testflinger-agent-host>`
* **Agents**: :doc:`Manage agents <how-to/administer-agent-hosts/manage-agents>` • :doc:`Agent configuration <reference/testflinger-agent-conf>` • :doc:`Agents explained <explanation/agents>`
* **Device connectors**: :doc:`Connector types <reference/device-connector-types>` • :doc:`Connector configuration <reference/device-connector-conf>` • :doc:`MAAS storage <reference/maas_storage>`

Security
~~~~~~~~

Understand how Testflinger protects credentials and data, and how to configure your deployment to meet your security requirements.

* **Trust model**: :doc:`Security overview <explanation/security>`
* **Deep dives**: :doc:`How authentication works <explanation/authentication>` •  :doc:`OIDC authentication <explanation/oidc-auth>` • :doc:`Secrets concepts <explanation/secrets>` • :doc:`Secrets reference <reference/secrets>`


---------

How this documentation is organised
-----------------------------------

This documentation uses the `Diátaxis documentation structure <https://diataxis.fr/>`_ .

* :doc:`Tutorial <tutorial/index>` takes you step-by-step through submitting your
  first job with Testflinger.
* :doc:`How-to guides <how-to/index>` provide instructions for specific tasks
  like submitting jobs, reserving machines, and administering a deployment.
* :doc:`Reference <reference/index>` provides technical specifications: job
  schemas, configuration files, and the REST API.
* :doc:`Explanation <explanation/index>` provides conceptual context about
  architecture, queues, security, and reservation.

---------

Project and community
---------------------

Testflinger is a member of the Ubuntu family. It is an open source project that
warmly welcomes community contributions, suggestions, fixes and constructive
feedback.

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