Workshop-backed development DUTs
================================

The project Workshop can provide a development DUT without granting a
Testflinger agent, device connector, or test container access to LXD. The
server and agent run in the ``dev`` Workshop; a separately managed sibling
Workshop named ``dut`` is the test device initialized by a test-only SDK.

The host owns the DUT lifecycle. The agent reaches the DUT directly on its SSH
port through Workshop's private bridge network. Workshop assigns each instance
a unique LXD hostname in the ``workshop`` DNS domain, which is resolved when
the agent starts. This preserves the production trust boundary: test commands
operate a remote DUT and cannot create, destroy, or inspect Workshops.

The first implementation is deliberately single-DUT and serial. It exercises
agent registration, job state transitions, noprovision reachability checks,
test containers, reservations, cancellation, and cleanup. It does not model
image deployment. A project can define additional DUT Workshops with distinct
names; each instance receives its own unique bridge hostname.

Setup
-----

The source tree provides these files:

* ``.workshop/dut.yaml`` defines the sibling DUT.
* ``.workshop/dut-setup`` installs and enables SSH and authorizes the
  test-only development key for the default ``workshop`` user.
* ``agent/devel/noprovision-dut.yaml`` is the connector configuration template
  used from ``dev``.
* ``agent/devel/noprovision-agent.conf`` is the agent configuration used
  in ``dev`` by the launch recipe.

Start the server and DUT, then optionally verify the development network:

.. code-block:: console

   just workshop serve
   just workshop check-dut

The DUT check resolves the DUT's unique bridge hostname, writes the ignored
runtime connector configuration, and verifies that ``dev`` can reach it over
SSH:

.. code-block:: text

   dev -> <unique DUT hostname>.workshop:22

The DUT is initialized automatically at launch. The host creates a test-only
SSH key below ``agent/devel/.workshop_noprovision``; that directory is ignored
by Git. The DUT setup SDK installs and enables SSH and authorizes its public
key for the default ``workshop`` user. Jobs using this harness must set
``test_data.test_username: workshop``. The noprovision connector checks that
this initialized DUT is reachable when a job includes ``provision_data:
{skip: false}``. A failed check indicates development infrastructure needs
attention; the agent has no authority to recreate or reset the Workshop.

The default development agent uses the device-free ``fake_connector`` and runs
on the host, without a Workshop:

.. code-block:: console

   just agent::start

It does not start or require a DUT, so agent-only failure tests can run without
one. To start the Workshop DUT's noprovision agent instead:

.. code-block:: console

   just workshop::start-dut
   just workshop::check-dut
   just agent::start noprovision

The connector argument selects ``agent/devel/<connector>-agent.conf``. The DUT
check renders ``agent/devel/noprovision-dut.yaml`` with the resolved hostname
into the ignored runtime configuration used by the noprovision agent. Test
commands must connect to that address rather than assume they execute on the
DUT.

The optional second argument selects the Testflinger server URL. It defaults to
the server in ``dev``. For example, a host-run fake agent can use a separately
running server:

.. code-block:: console

   just agent::start fake_connector http://server.example:5000

The URL is written only to the runtime agent configuration in ``dev``; the
committed agent configuration remains unchanged.

The target development server must have run ``create_sample_users.py``. It
creates the generic ``testflinger-agent`` credential used by the development
token helper. This credential has the ``agent`` role and is separate from the
portal sample users.

Stop the DUT only from the host:

.. code-block:: console

   just workshop dut-stop

Connector development scope
---------------------------

The sibling Workshop is appropriate for the common connector contract:
configuration parsing, phase dispatch, provision failure reporting, recovery
exit code handling, test-container network access, SSH readiness, and cleanup.
It can also exercise connectors whose side effects are expressed entirely via
a remote control service designed for the harness.

It cannot faithfully validate connectors that require physical media,
power-control hardware, serial devices, PXE/DHCP topology, firmware, UEFI, or
host LXD authority. Do not mount the host LXD socket or Workshop credentials
into ``dev`` to work around those limits.

If testing a connector needs more than the noprovision lifecycle, add a
test-only ``workshop`` connector only after its contract is defined. It should
call a narrowly scoped host controller API with operations such as ``reset``,
``reboot``, and ``status`` for a pre-allocated DUT. The controller must own
Workshop lifecycle and cleanup, authenticate the request, constrain the DUT
name to the job allocation, and expire orphaned allocations. It must not
accept arbitrary Workshop or shell commands.

This allows limited development testing of recovery and provisioning state
transitions without presenting the harness as equivalent to a hardware lab.
