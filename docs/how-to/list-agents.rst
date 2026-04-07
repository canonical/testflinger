.. _listing_agents:

Listing Agents
==============

A list of agents communicating with the server can be fetched via the command
line and displayed in several formats. When collecting the list of agents for
display, a variety of filters may also be applied. Aside from the filter for
status, the filters all support use of regular expressions.

The ``list-agents`` subcommand can provide output in three different modes:

- Table output (default)

  - Columns specified by comma separated list via ``--fields``

- Status summary (``--summary``)

- Single-column list of agent names (``-1``)

In all cases, filtering can be applied to various fields, e.g:

- Status can be filtered by specifying a list of included and excluded states

  - Available states include: ``online``, ``offline``, and ``maintenance``

    - Fine-grained online states are also available: ``waiting``, ``setup``,
      ``provision``, ``firmware_update``, ``test``, ``allocate``, ``reserve``,
      ``cleanup``

  - States can be *excluded* if they are preceded by a caret (``^``)

    - e.g.: ``--filter-status online,^waiting``

- Several other agent properties can also be filtered on using regular expression
  matching. All of these take the form of ``--filter-<attribute>`` and will apply
  regular expression matching against the agent's attribute value:

  - ``--filter-name``

  - ``--filter-queues``

  - ``--filter-location``

  - ``--filter-provision-type``

  - ``--filter-comment``

Table mode (default)
-------------------------

If neither ``-1`` nor ``--summary`` are specified, the default is to output a
table of agents matching the specified filters. The table fields can be selected
by specifying a comma-separated list of fields via ``--fields``, including any
of: name, status, location, provision_type, comment, job_id, queues. By default
name, status, location, provision_type, and comment are displayed.

.. code-block:: shell

  $ testflinger list-agents
  Name     Status   Location  Provision Type  Comment
  ---------------------------------------------------
  audino   waiting  TXR3-DH1  maas2
  multi-3  waiting            multi
  petilil  waiting  TXR3-DH1  maas2

Summary mode (--summary)
----------------------------

.. code-block:: shell

  $ testflinger list-agents --summary
  Online:           2413
    waiting          2328
    provision        28
    test             30
    reserve          27

  Offline:          63
    offline          55
    maintenance      8

Filtering, of course can be used with any output mode, for example:

.. code-block:: shell

  $ testflinger list-agents --summary --filter-status online,^waiting
  Online:           78
    provision        14
    test             12
    reserve          52

  Offline:          0

.. _list-agents-scripting:

Single-column list mode (-1)
------------------------------

If the purpose of listing the agents is intended to drive shell scripting, it
may be desirable to have a single list of agent names. In single-column list
mode (``-1``) output is suitable for further processing in shell scripts very
much like ``ls -1`` would be used for files.

Here's an example where the agents selected by the filter are set to ``online``
within a for loop:

.. code-block:: shell

  $ for agent in $(testflinger list-agents --filter-queue "petilil|audino" -1); do testflinger admin set agent-status --agents $agent --status online; done
  Agent audino status is now: waiting
  Agent petilil status is now: waiting

.. tip::

   This can be particularly useful in combination with ``--filter-comment``
   if good comments are made as agents are brought offline.
