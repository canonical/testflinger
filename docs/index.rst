:relatedlinks: [Diátaxis](https://diataxis.fr/)

.. _home:

Testflinger
============

.. A single sentence that says what the product is, succinctly and memorably.

Testflinger is a system for orchestrating the time-sharing of access to a pool of
target machines.

.. A paragraph of one to three short sentences, that describe what the product does.

Each Testflinger system consists of:

* a web service (called just Testflinger) that provides an API to request jobs
  by placing them on a queue
* per machine agents that wait for jobs to placed on queues they can service
  and then process them

Jobs can be either fully automated scripts that can attempt to complete within
the allocated time or interactive shell sessions.

.. A third paragraph of similar length, this time explaining what need the product meets.

The Testflinger system is particular useful for sharing finite machine resources
between different consumers in a predictable fashion.
 

.. Finally, a paragraph that describes whom the product is useful for.

Typically this has been used for managing a test lab where CI/CD test runs and
also exploratory testing by human operators is desired.

---------

In this documentation
---------------------

..  grid:: 1 1 2 2

   ..  grid-item:: :doc:`Tutorial <tutorial/index>`

       **Start here**: a hands-on introduction to Testflinger for new users

   ..  grid-item:: :doc:`How-to guides <how-to/index>`

      **Step-by-step guides** covering key operations and common tasks

.. grid:: 1 1 2 2
   :reverse:

   .. grid-item:: :doc:`Reference <reference/index>`

      **Technical information** - specifications, APIs, architecture

   .. grid-item:: :doc:`Explanation <explanation/index>`

      **Discussion and clarification** of key topics

---------

Project and community
---------------------

Testflinger is a member of the Ubuntu family. It's an open source project that
warmly welcomes community projects, contributions, suggestions, fixes and
constructive feedback.

* This project follows the `Ubuntu Code of Conduct`_
* This project is `hosted on GitHub`_, contributions welcome
* :ref:`Thinking about using Testflinger for your next project? Get in touch! <home>`


.. toctree::
   :hidden:
   :maxdepth: 2

   tutorial/index
   how-to/index
   reference/index
   explanation/index

.. _Ubuntu Code of Conduct: https://ubuntu.com/community/ethos/code-of-conduct
.. _hosted on GitHub: https://github.com/canonical/testflinger
