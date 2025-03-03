# Copyright (C) 2024 Canonical
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

"""Zapper Connector for IOT provisioning."""
import logging
from typing import Any, Dict, Tuple
from testflinger_device_connectors.devices.zapper import ZapperConnector
from testflinger_device_connectors.devices import ProvisioningError
from testflinger_device_connectors.devices.zapper_iot.parser import (
    validate_provision_plan,
    validate_urls,
)

logger = logging.getLogger(__name__)


class DeviceConnector(ZapperConnector):
    """Tool for provisioning baremetal with a given image."""

    PROVISION_METHOD = "ProvisioningIoT"

    def _validate_configuration(
        self,
    ) -> Tuple[Tuple, Dict[str, Any]]:
        """
        Validate the job config and data and prepare the arguments
        for the Zapper `provision` API.
        """

        username = self.job_data.get("test_data", {}).get(
            "test_username", "ubuntu"
        )
        password = self.job_data.get("test_data", {}).get(
            "test_password", "ubuntu"
        )

        ubuntu_sso_email = self.job_data["provision_data"].get(
            "ubuntu_sso_email", ""
        )

        provisioning_data = {
            "username": username,
            "password": password,
            "preset": self.job_data["provision_data"].get("preset"),
            "reboot_script": self.config["reboot_script"],
        }

        provision_plan = self.job_data["provision_data"].get("provision_plan")
        if provision_plan:

            try:
                # Make sure the user created at provision time is
                # the same used during the test phase.
                provision_plan["config"]["username"] = username
                provision_plan["config"]["password"] = password

                # If the initial login is using console-conf, we need to
                # check if the user has provided an ubuntu_sso_email.
                # If not, we raise an error.
                # ubuntu_sso_email will be used to set the username for the
                # initial login.
                run_stages = provision_plan["run_stage"]
                for stage in run_stages:
                    if (
                        isinstance(stage, dict)
                        and "initial_login" in stage.keys()
                        and stage["initial_login"].get("method")
                        == "console-conf"
                    ):
                        if ubuntu_sso_email:
                            provision_plan["config"][
                                "username"
                            ] = ubuntu_sso_email
                            break
                        else:
                            raise ValueError(
                                "ubuntu_sso_email is required "
                                "when initial login using console-conf"
                            )

                validate_provision_plan(provision_plan)

                provisioning_data["custom_provision_plan"] = provision_plan
            except (ValueError, KeyError) as e:
                raise ProvisioningError from e
        # If there is an ubuntu_sso_email and no provision plan, we use it
        # as the username.
        elif ubuntu_sso_email:
            provisioning_data["username"] = ubuntu_sso_email

        urls = self.job_data["provision_data"].get("urls", [])
        try:
            validate_urls(urls)
        except ValueError as e:
            raise ProvisioningError from e
        provisioning_data["urls"] = urls

        return ((), provisioning_data)

    def _post_run_actions(self, args):
        """Run further actions after Zapper API returns successfully."""
        super()._post_run_actions(args)

        # Default to do copy the ssh id.
        do_copy_ssh_id = True

        provision_plan = self.job_data["provision_data"].get("provision_plan")
        # If provision plan is provided, we check if the initial login
        # is using console-conf. If so, we do not copy the ssh id.
        if provision_plan:
            run_stages = provision_plan["run_stage"]
            for stage in run_stages:
                if (
                    isinstance(stage, dict)
                    and "initial_login" in stage.keys()
                    and stage["initial_login"].get("method") == "console-conf"
                ):
                    do_copy_ssh_id = False
                    break
        # If no provision plan is provided, we check if the user has
        # provided an ubuntu_sso_email. If so, we do not copy the ssh id.
        else:
            ubuntu_sso_email = self.job_data["provision_data"].get(
                "ubuntu_sso_email", ""
            )
            if ubuntu_sso_email:
                do_copy_ssh_id = False

        if do_copy_ssh_id:
            self._copy_ssh_id()
