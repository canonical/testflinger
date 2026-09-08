# Copyright (C) 2024 Canonical
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
"""Unit tests for Testflinger enums."""

from itertools import pairwise

import pytest
from testflinger_common.enums import (
    AgentMode,
    AgentState,
    JobState,
    ServerRoles,
    TestPhase,
)


class TestServerRoles:
    """Test ServerRoles enum."""

    def test_compare_with_next(self, sorted_roles):
        """Test consecutive pairs of roles."""
        for lower, higher in pairwise(sorted_roles):
            assert lower < higher
            assert not (lower >= higher)
            assert lower <= higher
            assert not (lower > higher)
            assert higher > lower
            assert not (higher <= lower)
            assert higher >= lower
            assert not (higher < lower)

    def test_compare_with_self(self, sorted_roles):
        """Test with same role."""
        for role in sorted_roles:
            assert role == role
            assert role <= role
            assert role >= role
            assert not (role != role)
            assert not (role < role)
            assert not (role > role)

    def test_comparison_type_error(self):
        """Test that comparing with non-ServerRoles raises TypeError."""
        with pytest.raises(
            TypeError, match="Cannot compare ServerRoles to str"
        ):
            ServerRoles.ADMIN < "admin"  # noqa: B015

        with pytest.raises(
            TypeError, match="Cannot compare ServerRoles to int"
        ):
            ServerRoles.ADMIN < 1  # noqa: B015

        with pytest.raises(
            TypeError, match="Cannot compare ServerRoles to NoneType"
        ):
            ServerRoles.ADMIN < None  # noqa: B015

    def test_role_ordering(self, sorted_roles):
        """Test that roles are ordered by privilege hierarchy."""
        assert sorted(ServerRoles) == sorted_roles


class TestPhaseEnumInvariants:
    """Enforce superset relationships: TestPhase, AgentState, JobState."""

    def test_agent_state_is_superset_of_test_phase(self):
        """AgentState must include every TestPhase value."""
        assert {phase.value for phase in TestPhase} <= {
            state.value for state in AgentState
        }

    def test_job_state_is_superset_of_test_phase(self):
        """JobState must include every TestPhase value."""
        assert {phase.value for phase in TestPhase} <= {
            state.value for state in JobState
        }

    def test_agent_mode_values(self):
        """AgentMode must contain exactly the four expected modes."""
        assert set(AgentMode) == {
            AgentMode.ONLINE,
            AgentMode.MAINTENANCE,
            AgentMode.OFFLINE,
            AgentMode.RESTART,
        }


class TestAgentModeSubstate:
    """Which modes are qualified by an AgentState, and which are not."""

    @pytest.mark.parametrize("mode", [AgentMode.ONLINE, AgentMode.MAINTENANCE])
    def test_modes_with_a_substate(self, mode):
        """ONLINE and MAINTENANCE are qualified by a sub-state."""
        assert mode.has_substate

    @pytest.mark.parametrize("mode", [AgentMode.OFFLINE, AgentMode.RESTART])
    def test_modes_without_a_substate(self, mode):
        """OFFLINE and RESTART describe the agent completely."""
        assert not mode.has_substate


class TestAgentModeFromState:
    """Inferring a mode from a bare agent state."""

    @pytest.mark.parametrize(
        "state",
        [AgentMode.OFFLINE, AgentMode.RESTART, AgentMode.MAINTENANCE],
    )
    def test_state_that_names_a_mode(self, state):
        """The three states that named a mode map to that mode."""
        assert AgentMode.from_state(state) == AgentMode(state)

    @pytest.mark.parametrize(
        "state",
        [AgentState.WAITING, AgentState.PROVISION, AgentState.TEST],
    )
    def test_state_of_a_working_agent(self, state):
        """Any other state is something an agent does while online."""
        assert AgentMode.from_state(state) == AgentMode.ONLINE

    @pytest.mark.parametrize("state", [None, "", "unknown"])
    def test_absent_or_unrecognised_state(self, state):
        """A record that says nothing useful is assumed to be online."""
        assert AgentMode.from_state(state) == AgentMode.ONLINE
