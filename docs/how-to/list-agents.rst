.. _listing_agents:

Listing Agents
==============

A list of agents communicating with the server can be fetched via the command
line and displayed in several formats. When collecting the list of agents for
display, a variety of filters may also be applied.

The ``list-agents`` subcommand can provide output in three different modes:

- Table output (default)

  - Columns specified by comma separated list via ``--fields``

- Status summary (``--summary``)

- Single-column list of agent names (``-1``)

Agent Mode and State
--------------------

Each agent has two independent status concepts:

**Mode** (gross)
  The agent's current operating mode, as reported by the agent itself:

  - ``online`` — active, processing jobs normally
  - ``maintenance`` — in maintenance, not processing new jobs
  - ``offline`` — offline, not processing jobs
  - ``restart`` — restarting

**State** (fine)
  The sub-state within the current mode, reported by the agent:

  - ``waiting`` — idle, ready for the next job
  - ``active`` — running any job phase (mnemonic for all non-waiting states)
  - ``setup``, ``provision``, ``firmware_update``, ``test``, ``allocate``,
    ``reserve``, ``cleanup`` — specific job execution phases

**Commanded Mode**
  The mode an administrator has instructed the agent to adopt. The agent
  will transition to this mode after its current job completes. When
  ``commanded_mode`` differs from ``mode``, the agent is *pending* a
  transition. The ``commanded_mode`` column shows ``-`` when no transition
  is pending.

Display format in the ``mode`` column:
  ``online:test->maintenance`` — online, running a test, will go maintenance
  when the job finishes.

Filtering
---------

``--filter-mode``
  Filter by the agent's current mode. Use ``^`` prefix to exclude.

  Values: ``online``, ``offline``, ``maintenance``, ``restart``

  .. code-block:: shell

    # Only online or maintenance agents
    testflinger list-agents --filter-mode online,maintenance

    # Exclude offline agents
    testflinger list-agents --filter-mode ^offline

``--filter-state``
  Filter by sub-state. Use ``^`` prefix to exclude.

  Values: ``waiting``, ``active``, ``setup``, ``provision``,
  ``firmware_update``, ``test``, ``allocate``, ``reserve``, ``cleanup``

  ``active`` is a mnemonic for any sub-state except ``waiting``.

  .. code-block:: shell

    # Agents currently running a job
    testflinger list-agents --filter-state active

    # Online agents that are idle
    testflinger list-agents --filter-mode online --filter-state waiting

    # Online agents running a test specifically
    testflinger list-agents --filter-mode online --filter-state test

``--filter-commanded-mode``
  Filter by the commanded mode. Use ``^`` prefix to exclude.

  Values: ``online``, ``offline``, ``maintenance``, ``restart``, ``pending``

  ``pending`` is a mnemonic for agents where ``commanded_mode`` is set and
  differs from the current ``mode`` — i.e. a mode change has been commanded
  but not yet adopted.

  .. code-block:: shell

    # Agents with a pending mode change
    testflinger list-agents --filter-commanded-mode pending

    # Online agents commanded to go offline (still processing a job)
    testflinger list-agents --filter-mode online --filter-commanded-mode offline

    # Agents commanded online but not yet there
    testflinger list-agents --filter-commanded-mode online,^pending

Combining filters uses AND semantics — all specified filters must match.
Within a single filter, comma-separated values use OR semantics.

Other filters (all support regular expression matching):

- ``--filter-name``
- ``--filter-queues``
- ``--filter-location``
- ``--filter-provision-type``
- ``--filter-comment``

Table mode (default)
--------------------

If neither ``-1`` nor ``--summary`` are specified, the default is to output a
table of agents. The fields can be selected via ``--fields`` (comma-separated).

Available fields: ``name``, ``mode``, ``state``, ``commanded_mode``,
``location``, ``provision_type``, ``comment``, ``job_id``, ``submitted_by``,
``queues``.

Default fields: ``name``, ``mode``, ``state``, ``commanded_mode``,
``location``, ``provision_type``, ``comment``.

The ``commanded_mode`` column shows ``-`` when no transition is pending
(i.e. ``commanded_mode`` is absent or matches ``mode``).

.. code-block:: shell

  $ testflinger list-agents
  NAME     MODE    STATE    COMMANDED MODE  LOCATION  PROVISION TYPE  COMMENT
  -------------------------------------------------------------------------
  audino   online  waiting  -               TXR3-DH1  maas2
  multi-3  online  test     maintenance               multi
  petilil  online  waiting  -               TXR3-DH1  maas2

Summary mode (``--summary``)
----------------------------

.. code-block:: shell

  $ testflinger list-agents --summary
  MODE              COUNT
  online            2413
    waiting         2328
    provision         28
    test              30
    reserve           27
  maintenance          8
  offline             55

.. code-block:: shell

  $ testflinger list-agents --summary --filter-mode online --filter-state active
  MODE              COUNT
  online              85
    provision         14
    test              12
    reserve           52
    allocate           7

.. _list-agents-scripting:

Single-column list mode (``-1``)
---------------------------------

If the purpose of listing the agents is intended to drive shell scripting, it
may be desirable to have a single list of agent names. In single-column list
mode (``-1``) output is suitable for further processing in shell scripts very
much like ``ls -1`` would be used for files.

Here's an example where the agents selected by the filter are commanded to
``online`` within a for loop:

.. code-block:: shell

  $ for agent in $(testflinger list-agents --filter-queues "petilil|audino" -1); do testflinger admin set agent-status --agents $agent --mode online; done
  Agent audino commanded to mode 'online'.
  Agent petilil commanded to mode 'online'.

.. tip::

   This can be particularly useful in combination with ``--filter-comment``
   if good comments are made as agents are brought offline or into maintenance.
