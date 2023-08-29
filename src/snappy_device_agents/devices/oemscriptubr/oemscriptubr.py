# Copyright (C) 2023 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Ubuntu OEM Script UBR Provisioner support code.
this for systems that can use the oem recovery-from-iso.sh script
for provisioning, but require the --ubr flag in order to use the
"ubuntu recovery" method.
"""

import logging
from snappy_device_agents.devices.oemscript.oemscript import OemScript

logger = logging.getLogger()


class OemScriptUbr(OemScript):
    """Device Agent for UBR OEM Script."""

    # Extra arguments to pass to the OEM script
    extra_script_args = ["--ubr"]
