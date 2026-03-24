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

.. grid:: 1 1 2 2

   .. grid-item-card:: Tutorial
      :link: /tutorial/index
      :link-type: doc

      **Get started** - a hands-on introduction to Testflinger for new users

   .. grid-item-card:: How-to guides
      :link: /how-to/index
      :link-type: doc

      **Step-by-step guides** - covering key operations and common tasks

.. grid:: 1 1 2 2

   .. grid-item-card:: Reference
      :link: /reference/index
      :link-type: doc

      **Technical information** - specifications, APIs, architecture

   .. grid-item-card:: Explanation
      :link: /explanation/index
      :link-type: doc

      **Discussion and clarification** of key concepts

.. grid:: 1 1 2 2

   .. grid-item-card:: Testflinger Agent Hosts Administration
      :link: /how-to/administer-agent-hosts/index
      :link-type: doc

      **Administration** tasks and best practices for operators of Testflinger Agent Hosts

---------

Project and community
---------------------

Testflinger is a member of the Ubuntu family. It is an open source project that
warmly welcomes community contributions, suggestions, fixes and
constructive feedback.

* This project follows the `Ubuntu Code of Conduct`_
* This project is `hosted on GitHub`_ - contributions are welcome
* :ref:`Interested in using Testflinger for your project? Get in touch! <home>`


.. toctree::
   :hidden:
   :maxdepth: 2

   tutorial/index
   how-to/index
   reference/index
   explanation/index

.. _Ubuntu Code of Conduct: https://ubuntu.com/community/ethos/code-of-conduct
.. _hosted on GitHub: https://github.com/canonical/testflinger
