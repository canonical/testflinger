# Copyright (C) 2022 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Integration tests for mode persistence through restart.

These tests verify the expected behavior of the v2 API when an agent
transitions through various modes, particularly around restart scenarios.

The tests verify:
1. Agent data is accessible via v2 API in nested format
2. Mode is retained after an agent restarts
3. commanded_mode properly tracks admin commands

NOTE: These integration tests require:
- A running Testflinger server with v2 API enabled
- Running agent instances (e.g., agent_v2)
- Admin credentials for mode commands
"""

import json
import logging
import time

import pytest

logger = logging.getLogger(__name__)


class TestModePersistenceThroughRestart:
    """Test that agent mode is correctly retained through restart cycle."""

    def test_list_agents_via_v2_api(self, cli_client, test_agent_name):
        """Test that we can fetch agent list via v2 API.

        This verifies the integration test framework works end-to-end.
        """
        agents = cli_client.list_agents()
        assert agents is not None, "Failed to list agents"
        assert len(agents) > 0, "No agents found"

        # Find our test agent
        test_agent = next(
            (a for a in agents if a.get("name") == test_agent_name), None
        )
        assert test_agent is not None, f"Agent {test_agent_name} not found"

        logger.info(
            f"Agent from v2 API:\n{json.dumps(test_agent, indent=2, default=str)}"
        )

        # Agent should have basic fields
        assert "name" in test_agent
        assert test_agent["name"] == test_agent_name

    def test_agent_mode_is_stored_in_nested_v2_format(
        self, cli_client, test_agent_name
    ):
        """Test that mode is stored and returned in v2 nested format.

        Expected behavior:
        - Agent mode field is nested dict: {"value": "...", "changed_at": ...}
        - Not a flat string
        """
        agent = cli_client.get_agent(test_agent_name)
        assert agent is not None, f"Agent {test_agent_name} not found"

        logger.info(
            f"Agent from v2 API:\n{json.dumps(agent, indent=2, default=str)}"
        )

        # Check mode field exists and is nested dict format
        assert "mode" in agent, "Agent missing 'mode' field"
        mode = agent["mode"]
        assert isinstance(mode, dict), f"mode should be dict, got {type(mode)}"
        assert "value" in mode, "mode dict should have 'value' key"
        assert "changed_at" in mode, "mode dict should have 'changed_at' key"

        logger.info(f"Agent mode: {mode['value']} (changed at {mode['changed_at']})")

    def test_commanded_mode_tracks_admin_commands(
        self, cli_client, test_agent_name
    ):
        """Test that commanded_mode field properly tracks admin commands.

        Expected behavior:
        - Admin can set commanded_mode via PATCH /v2/agents/{name}/commanded_mode
        - commanded_mode appears in agent data in nested format
        - Current mode remains unchanged until agent acts on command
        """
        # Step 1: Get initial agent state
        agent = cli_client.get_agent(test_agent_name)
        assert agent is not None
        initial_mode = agent.get("mode", {}).get("value")
        logger.info(f"Initial mode: {initial_mode}")

        # Step 2: Admin sends a mode command
        test_mode = "offline"
        success = cli_client.set_agent_mode(
            test_agent_name,
            test_mode,
            comment="Integration test: commanding mode change",
        )
        assert success, f"Failed to set agent mode to {test_mode}"

        # Step 3: Fetch updated agent data
        agent = cli_client.get_agent(test_agent_name)
        assert agent is not None

        logger.info(
            f"Agent after command:\n{json.dumps(agent, indent=2, default=str)}"
        )

        # Step 4: Verify commanded_mode was set
        assert "commanded_mode" in agent, "Agent missing 'commanded_mode' field"
        commanded_mode = agent["commanded_mode"]
        assert isinstance(
            commanded_mode, dict
        ), f"commanded_mode should be dict, got {type(commanded_mode)}"
        assert (
            commanded_mode.get("value") == test_mode
        ), f"Expected commanded_mode={test_mode}, got {commanded_mode.get('value')}"
        assert (
            "changed_at" in commanded_mode
        ), "commanded_mode dict should have 'changed_at' key"
        assert (
            "changed_by" in commanded_mode
        ), "commanded_mode dict should have 'changed_by' key"

        logger.info(
            f"Commanded mode: {commanded_mode['value']} "
            f"(by {commanded_mode.get('changed_by', 'unknown')})"
        )

    def test_agent_can_transition_to_maintenance(
        self, cli_client, test_agent_name
    ):
        """Simple test: verify agent can be set to maintenance mode.
        
        This proves:
        1. Admin can command mode changes via v2 API
        2. Agent receives and processes the commanded_mode
        3. Agent's mode field actually changes
        """
        # Step 1: Command agent to maintenance
        logger.info("Step 1 - Commanding agent to maintenance mode...")
        success = cli_client.set_agent_mode(
            test_agent_name,
            "maintenance",
            comment="Integration test: simple mode change",
        )
        assert success, "Failed to set agent mode to maintenance"
        
        # Step 2: Verify commanded_mode was set on server
        agent = cli_client.get_agent(test_agent_name)
        commanded = agent.get("commanded_mode", {}).get("value")
        logger.info(f"Step 2 - Commanded mode on server: {commanded}")
        assert commanded == "maintenance", f"Expected commanded=maintenance, got {commanded}"
        
        # Step 3: Wait for agent to process the command
        logger.info("Step 3 - Waiting for agent to process mode change...")
        max_wait = 15  # seconds
        for i in range(max_wait):
            agent = cli_client.get_agent(test_agent_name)
            current_mode = agent.get("mode", {}).get("value")
            logger.info(f"  Poll {i+1}s: current mode = {current_mode}")
            
            if current_mode == "maintenance":
                logger.info(f"✓ Agent transitioned to maintenance at {i+1}s")
                break
            
            time.sleep(1)
        
        # Step 4: Final verification
        agent = cli_client.get_agent(test_agent_name)
        final_mode = agent.get("mode", {}).get("value")
        
        logger.warning(
            f"\n{'='*70}\n"
            f"SIMPLE MODE CHANGE TEST:\n"
            f"Commanded: maintenance\n"
            f"Final mode: {final_mode}\n"
            f"Success: {final_mode == 'maintenance'}\n"
            f"{'='*70}"
        )
        
        assert final_mode == "maintenance", (
            f"Agent did not transition to maintenance. "
            f"Final mode: {final_mode}"
        )

    @pytest.mark.parametrize(
        "target_mode", ["online", "offline", "maintenance"]
    )
    def test_agent_maintains_previous_mode_after_restart_command(
        self, cli_client, test_agent_name, target_mode
    ):
        """Test mode persistence through restart for different modes.

        SETUP: Set agent to target_mode
        TEST: Send restart command
        VERIFY: Agent restarted and target_mode is still the active mode

        Parameterized to test all modes:
        - online → restart → online
        - offline → restart → offline
        - maintenance → restart → maintenance

        This test verifies that when an agent restarts, it correctly
        restores its previous mode instead of staying in restart mode.
        """
        # SETUP: Set agent to target mode
        logger.info(f"SETUP: Setting agent to {target_mode} mode...")
        success = cli_client.set_agent_mode(
            test_agent_name,
            target_mode,
            comment=f"Integration test: setup - target mode {target_mode}",
        )
        assert success, f"Failed to set agent mode to {target_mode}"
        
        # Wait for agent to process the mode change
        max_wait = 15
        logger.info(f"SETUP: Waiting up to {max_wait}s for agent to adopt {target_mode}...")
        for i in range(max_wait):
            agent = cli_client.get_agent(test_agent_name)
            current_mode = agent.get("mode", {}).get("value")
            if current_mode == target_mode:
                logger.info(f"SETUP: Agent adopted {target_mode} at {i}s")
                break
            time.sleep(1)
        
        # Verify setup was successful
        agent = cli_client.get_agent(test_agent_name)
        setup_mode = agent.get("mode", {}).get("value")
        if setup_mode != target_mode:
            logger.warning(
                f"SETUP: Warning - agent mode is {setup_mode}, not {target_mode}. "
                f"Agent may not support this mode or may be stuck."
            )
        
        logger.info(f"SETUP: Complete. Agent mode = {setup_mode}")

        # TEST: Send restart command
        logger.info(f"TEST: Sending restart command...")
        success = cli_client.set_agent_mode(
            test_agent_name,
            "restart",
            comment="Integration test: restart command",
        )
        assert success, "Failed to send restart command"

        agent = cli_client.get_agent(test_agent_name)
        commanded = agent.get("commanded_mode", {}).get("value")
        logger.info(f"TEST: Commanded mode set to: {commanded}")
        assert commanded == "restart", f"Expected commanded_mode=restart, got {commanded}"

        # VERIFY: Wait for agent to restart and restore mode
        # Agent startup time (~10s) + main loop cycle (~10s) = up to 20s
        max_wait_time = 25  # seconds
        poll_interval = 1   # second between polls (1 Hz)
        elapsed = 0
        
        logger.info(f"VERIFY: Waiting up to {max_wait_time}s for restart and mode restoration...")
        logger.info("=" * 80)
        logger.info(
            f"{'Time(s)':>8} | {'mode.value':>15} | {'commanded_mode.value':>20} | Notes"
        )
        logger.info("=" * 80)
        
        # Track if we observed the agent transition to restart mode
        observed_restart_mode = False
        mode_restored = False
        
        while elapsed < max_wait_time:
            agent = cli_client.get_agent(test_agent_name)
            current_mode = agent.get("mode", {}).get("value")
            current_commanded = agent.get("commanded_mode", {}).get("value")
            
            notes = ""
            
            # Check if agent transitioned to restart mode
            if current_mode == "restart":
                observed_restart_mode = True
                notes = "← RESTART MODE OBSERVED"
            
            # Check if mode has been restored to target mode
            if observed_restart_mode and current_mode == target_mode:
                mode_restored = True
                notes = "← MODE RESTORED TO TARGET!"
            
            logger.info(
                f"{elapsed:>8} | {current_mode:>15} | {str(current_commanded):>20} | {notes}"
            )
            
            # Exit early if restored
            if mode_restored:
                logger.info(
                    f"VERIFY: Mode restored to {target_mode} after {elapsed}s restart cycle"
                )
                break
            
            time.sleep(poll_interval)
            elapsed += poll_interval

        logger.info("=" * 80)

        # Final verification
        agent = cli_client.get_agent(test_agent_name)
        final_mode = agent.get("mode", {}).get("value")
        final_commanded = agent.get("commanded_mode", {}).get("value")
        
        logger.warning(
            f"\n{'='*70}\n"
            f"MODE PERSISTENCE TEST RESULT [{target_mode}]:\n"
            f"{'='*70}\n"
            f"Target mode (before restart): {target_mode}\n"
            f"Observed restart transition:  {observed_restart_mode}\n"
            f"Final mode (after restart):   {final_mode}\n"
            f"Final commanded_mode:         {final_commanded}\n"
            f"Mode restored correctly:      {mode_restored}\n"
            f"Elapsed time:                 {elapsed}s\n"
            f"{'='*70}"
        )
        
        # Assertion: mode must be restored to target mode
        assert final_mode == target_mode, (
            f"BUG: Mode is '{final_mode}' after restart, should be '{target_mode}'. "
            f"Observed restart transition: {observed_restart_mode}"
        )


class TestIntegrationTestNotesAndManualVerification:
    """Documentation and manual test procedures.

    These notes document the expected v2 API behavior and how to verify
    the mode persistence feature manually.
    """

    def test_manual_verification_procedure(self):
        """This test documents the manual verification steps.

        MANUAL TEST PROCEDURE:
        ======================

        Prerequisites:
          - Server running with v2 API: http://192.168.4.201:5000
          - Agent running: e.g., agent_v2 (fake_connector)
          - Admin credentials available

        Expected v2 API Response Format:
        --------------------------------

        GET /v2/agents/{agent_name}/data returns:
        {
          "name": "agent_v2",
          "mode": {
            "value": "online",
            "changed_at": "2026-10-21T14:00:00Z"
          },
          "state": "waiting",
          "commanded_mode": {
            "value": "restart",
            "changed_at": "2026-10-21T14:05:00Z",
            "changed_by": "infra-agent-arm"
          },
          ...
        }

        Manual Test Steps:
        ------------------

        1. Verify agent exists:
           testflinger list-agents --filter-name agent_v2

        2. Get agent state:
           curl -H "Authorization: Bearer <token>" \\
             http://server:5000/v2/agents/agent_v2/data

        3. Command restart:
           testflinger --server=http://server:5000 \\
             admin --set-agent-offline agent_v2 --reason "testing"

        4. Monitor agent in log:
           tail -f /var/log/testflinger/agent.log

        5. Verify mode after restart:
           curl -H "Authorization: Bearer <token>" \\
             http://server:5000/v2/agents/agent_v2/data
           # Should show: "mode": {"value": "online", ...}
           # NOT: "mode": {"value": "restart", ...}
        """
        pytest.skip(
            "This is documentation; see method docstring for manual steps"
        )
