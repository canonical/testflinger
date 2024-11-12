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
"""Unit tests for muxpi device connector"""
import unittest
from unittest.mock import patch
from unittest.mock import Mock, ANY
from subprocess import CalledProcessError
from testflinger_device_connectors.devices.muxpi.muxpi import MuxPi
from testflinger_device_connectors.devices.muxpi.image import (
    Image,
    ImageType,
    PEImage,
    CEImage,
    PEImageVariant,
)

MUXPI_MODULE_NAME = "testflinger_device_connectors.devices.muxpi.muxpi.MuxPi"


class AnyStringWith(str):
    def __eq__(self, x):
        return self in str(x)


class MuxPiConnectorTests(unittest.TestCase):
    """Unit tests for MuxPi  class."""

    @patch(f"{MUXPI_MODULE_NAME}._run_control")
    @patch(f"{MUXPI_MODULE_NAME}._configure_sudo")
    @patch(f"{MUXPI_MODULE_NAME}._copy_to_control")
    def test_create_user_pe_tegra(
        self,
        mock__copy_to_control: Mock,
        mock__configure_sudo: Mock,
        mock__run_control: Mock,
    ):
        muxpi = MuxPi()
        muxpi.create_user(PEImage(variant=PEImageVariant.TEGRA))

        mock__run_control.assert_any_call(
            AnyStringWith("var/lib/cloud/seed/nocloud")
        )

        assert mock__run_control.call_count == 5
        assert mock__configure_sudo.call_count == 1

    @patch(f"{MUXPI_MODULE_NAME}._run_control")
    @patch(f"{MUXPI_MODULE_NAME}._configure_sudo")
    @patch(f"{MUXPI_MODULE_NAME}._copy_to_control")
    def test_create_user_ce_24_beyond(
        self,
        mock__copy_to_control: Mock,
        mock__configure_sudo: Mock,
        mock__run_control: Mock,
    ):

        muxpi = MuxPi()
        muxpi.create_user(CEImage(release="ce-oem-iot-24-and-beyond"))
        mock__run_control.assert_any_call(
            AnyStringWith("var/lib/cloud/seed/nocloud")
        )
        assert mock__run_control.call_count == 6
        assert mock__configure_sudo.call_count == 1
        assert mock__copy_to_control.call_count == 3

    @patch(f"{MUXPI_MODULE_NAME}._run_control")
    @patch(f"{MUXPI_MODULE_NAME}._configure_sudo")
    @patch(f"{MUXPI_MODULE_NAME}._copy_to_control")
    def test_create_user_ce_24_before(
        self,
        mock__copy_to_control: Mock,
        mock__configure_sudo: Mock,
        mock__run_control: Mock,
    ):

        muxpi = MuxPi()
        muxpi.create_user(CEImage(release="ce-oem-iot-before-24"))
        mock__run_control.assert_any_call(AnyStringWith("/system-boot"))
        assert mock__run_control.call_count == 6
        assert mock__configure_sudo.call_count == 1
        assert mock__copy_to_control.call_count == 3

    @patch(f"{MUXPI_MODULE_NAME}._run_control")
    @patch(f"{MUXPI_MODULE_NAME}._copy_to_control")
    def test_create_user_core20(
        self,
        mock__copy_to_control: Mock,
        mock__run_control: Mock,
    ):
        # uc20/99_nocloud.cfg
        muxpi = MuxPi()
        muxpi.create_user(Image(image_type=ImageType.CORE20))
        mock__copy_to_control.assert_any_call(
            AnyStringWith("uc20/99_nocloud.cfg"), ANY
        )
        mock__run_control.assert_any_call(
            AnyStringWith("ubuntu-seed/data/etc/cloud")
        )
        assert mock__run_control.call_count == 3
        assert mock__copy_to_control.call_count == 1

    @patch(f"{MUXPI_MODULE_NAME}._run_control")
    @patch(f"{MUXPI_MODULE_NAME}._configure_sudo")
    @patch(f"{MUXPI_MODULE_NAME}._copy_to_control")
    def test_create_user_pi_desktop(
        self,
        mock__copy_to_control: Mock,
        mock__configure_sudo: Mock,
        mock__run_control: Mock,
    ):

        muxpi = MuxPi()
        muxpi.create_user(Image(image_type=ImageType.PI_DESKTOP))
        mock__copy_to_control.assert_any_call(
            AnyStringWith("pi-desktop/oem-config.service"), ANY
        )
        mock__run_control.assert_any_call(
            AnyStringWith("/writable/lib/systemd/system/oem-config.service")
        )
        mock__copy_to_control.assert_any_call(
            AnyStringWith("pi-desktop/preseed.cfg"), ANY
        )
        mock__run_control.assert_any_call(
            AnyStringWith("/writable/preseed.cfg")
        )
        mock__run_control.assert_any_call(
            AnyStringWith("/etc/systemd/system/oem-config.target.wants")
        )
        assert mock__run_control.call_count == 4
        assert mock__copy_to_control.call_count == 2
        assert mock__configure_sudo.call_count == 1

    @patch(f"{MUXPI_MODULE_NAME}._run_control")
    @patch(f"{MUXPI_MODULE_NAME}._configure_sudo")
    @patch(f"{MUXPI_MODULE_NAME}._copy_to_control")
    def test_create_user_ubuntu_cpc(
        self,
        mock__copy_to_control: Mock,
        mock__configure_sudo: Mock,
        mock__run_control: Mock,
    ):

        muxpi = MuxPi()
        muxpi.create_user(Image(image_type=ImageType.UBUNTU_CPC))
        mock__run_control.assert_any_call(
            AnyStringWith("cloudimg-rootfs/var/lib/cloud/seed/nocloud-net")
        )
        mock__copy_to_control.assert_any_call(
            AnyStringWith("classic/meta-data"), ANY
        )
        mock__run_control.assert_any_call(AnyStringWith("meta-data"))
        mock__copy_to_control.assert_any_call(
            AnyStringWith("classic/user-data"), ANY
        )
        mock__run_control.assert_any_call(AnyStringWith("user-data"))
        assert mock__run_control.call_count == 4
        assert mock__copy_to_control.call_count == 2
        assert mock__configure_sudo.call_count == 0

    @patch(f"{MUXPI_MODULE_NAME}._run_control")
    @patch(f"{MUXPI_MODULE_NAME}._configure_sudo")
    @patch(f"{MUXPI_MODULE_NAME}._copy_to_control")
    def test_create_user_ubuntu(
        self,
        mock__copy_to_control: Mock,
        mock__configure_sudo: Mock,
        mock__run_control: Mock,
    ):

        muxpi = MuxPi()
        muxpi.create_user(Image(image_type=ImageType.UBUNTU))
        mock__run_control.assert_any_call(
            AnyStringWith("writable/var/lib/cloud/seed/nocloud-net")
        )
        mock__copy_to_control.assert_any_call(
            AnyStringWith("classic/meta-data"), ANY
        )
        mock__run_control.assert_any_call(AnyStringWith("meta-data"))
        mock__copy_to_control.assert_any_call(
            AnyStringWith("classic/user-data"), ANY
        )
        mock__run_control.assert_any_call(AnyStringWith("user-data"))
        mock__run_control.assert_any_call(
            AnyStringWith("etc/cloud/cloud.cfg.d/99-fake?cloud.cfg")
        )
        assert mock__run_control.call_count == 5
        assert mock__copy_to_control.call_count == 2
        assert mock__configure_sudo.call_count == 0

    @patch(f"{MUXPI_MODULE_NAME}.get_pe_image", return_value=None)
    @patch(f"{MUXPI_MODULE_NAME}.get_ce_oem_iot_image", return_value=None)
    @patch("subprocess.check_output", side_effect=CalledProcessError(1, "cmd"))
    def test_get_image_unknown(
        self,
        mock_subprocess,
        mock_ce_oem_iot_image,
        mock_get_pe_image,
    ):
        """Test get_image"""

        muxpi = MuxPi()
        assert muxpi.get_image() is None

    @patch(f"{MUXPI_MODULE_NAME}.get_ce_oem_iot_image", return_value=None)
    @patch(f"{MUXPI_MODULE_NAME}._run_control")
    def test_get_image_pe_image_tegra(
        self,
        mock__run_control,
        mock_get_ce_oem_iot_image,
    ):
        """Test get_image for tegra variant"""

        muxpi = MuxPi()
        image: PEImage = muxpi.get_image()
        assert image is not None
        assert image.variant == PEImageVariant.TEGRA

    def test_get_pe_image_tegra(self):
        """Test get_pe_image tegra variant"""

        def subprocess_side_effect(ssh_cmd, **kwargs):
            if "tegra" in "".join(ssh_cmd):
                return "yep tegra"
            raise CalledProcessError(1, "cmd")

        with patch(
            "subprocess.check_output", side_effect=subprocess_side_effect
        ):
            muxpi = MuxPi()
            image: PEImage = muxpi.get_image()
            assert isinstance(image, PEImage)

    def test_get_ce_oem_iot_image(self):
        """Test get_ce_oem_iot_image."""
        series = "2404"
        with patch("subprocess.check_output", return_value=series.encode()):
            muxpi = MuxPi()
            assert (
                muxpi.get_ce_oem_iot_image().release
                == "ce-oem-iot-24-and-beyond"
            )

        series = "2204"
        with patch("subprocess.check_output", return_value=series.encode()):
            muxpi = MuxPi()
            assert (
                muxpi.get_ce_oem_iot_image().release == "ce-oem-iot-before-24"
            )

        series = "24"
        with patch("subprocess.check_output", return_value=series.encode()):
            muxpi = MuxPi()
            assert (
                muxpi.get_ce_oem_iot_image().release
                == "ce-oem-iot-24-and-beyond"
            )

        series = "20"
        with patch("subprocess.check_output", return_value=series.encode()):
            muxpi = MuxPi()
            assert (
                muxpi.get_ce_oem_iot_image().release == "ce-oem-iot-before-24"
            )

        with patch(
            "subprocess.check_output", side_effect=CalledProcessError(1, "cmd")
        ):
            assert muxpi.get_ce_oem_iot_image() is None
