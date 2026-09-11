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


First steps
~~~~~~~~~~~

Install the client, run your first job, and learn the core workflow.

* **Get started**: :doc:`Tutorial <tutorial/index>` • :doc:`Install the CLI <how-to/install-cli>` • :doc:`CLI configuration <reference/cli-config>` • :doc:`Change server <how-to/change-server>`

Jobs
~~~~

The core unit of work: how a job is described, run, and used to reserve a machine.

* **Understand**: :doc:`Job schema <reference/job-schema>` • :doc:`Test phases <reference/test-phases>`
* **Run and manage**: :doc:`Submit a job <how-to/submit-job>` • :doc:`Retrieve results <how-to/retrieve-logs>` • :doc:`Cancel <how-to/cancel-job>` • :doc:`Search <how-to/search-job>`
* **Reserve a machine**: :doc:`Reserve a machine <how-to/reserve-job>` • :doc:`Extended reservation <explanation/extended-reservation>`

Queues, agents, and agent hosts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Queues route jobs to compatible agents to provision and operate the devices under test, and report the results. Agents run on agent hosts, which are VMs deployed with Juju.

* **Queues**: :doc:`Understand queues <explanation/queues>`
* **Extended capabilities**: :doc:`Restricted queues <explanation/restricted-queues>` • :doc:`Set job priority <how-to/job-priority>` • :doc:`How priority works <explanation/job-priority>`
* **Agents**: :doc:`List agents <how-to/list-agents>` • :doc:`Understand agents and agent hosts <explanation/agents>` • :doc:`Agent configuration <reference/testflinger-agent-conf>` • :doc:`Manage agents <how-to/administer-agent-hosts/manage-agents>`
* **Agent host administration**: :doc:`Deploy <how-to/administer-agent-hosts/deploy-testflinger-agent-host>` • :doc:`Maintain <how-to/administer-agent-hosts/maintain-testflinger-agent-host>`

Device connectors
~~~~~~~~~~~~~~~~~

Agents invoke device connectors to provision and operate devices under test (DUT). Each connector supports a particular provisioning type.

* **Device connectors**: :doc:`Connector types <reference/device-connector-types>` • :doc:`Connector configuration <reference/device-connector-conf>` • :doc:`MAAS storage <reference/maas_storage>`

Server
~~~~~~

A Kubernetes application that stores data, serves the API, and coordinates the system.

* **Understand**: :doc:`Architecture <explanation/architecture>`
* **Reference**: :doc:`Server configuration <reference/testflinger-server-conf>` • :doc:`REST API reference (OpenAPI) <reference/openapi>`
* **Administration**: :doc:`Deploy <how-to/administer-server/deploy-testflinger-server>` • :doc:`Maintain <how-to/administer-server/maintain-testflinger-server>`

Access and permissions
~~~~~~~~~~~~~~~~~~~~~~~~

Prove client identity and control what each client is allowed to do.

* **Authentication**: :doc:`Authenticate with the CLI <how-to/authentication>` • :doc:`How authentication works <explanation/authentication>`
* **Single sign-on (OIDC)**: :doc:`OIDC authentication <explanation/oidc-auth>` • :ref:`Enable OIDC <howto-enable-oidc>` • :doc:`OIDC configuration <reference/juju-oidc-config>`
* **Authorisation**: :doc:`API roles <reference/api-roles>` • :doc:`Manage client permissions <how-to/manage-client-permissions>` • :doc:`Create admin credentials <how-to/create-admin-user>`

Security
~~~~~~~~

How Testflinger protects credentials and data, and how to handle secrets safely.

* **Trust model**: :doc:`Security overview <explanation/security>`
* **Secrets**: :doc:`Use secrets <how-to/use-secrets>` • :doc:`Secrets concepts <explanation/secrets>` • :doc:`Secrets reference <reference/secrets>`


---------

How this documentation is organised
-----------------------------------

This documentation uses the `Diátaxis documentation structure <https://diataxis.fr/>`_.

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
