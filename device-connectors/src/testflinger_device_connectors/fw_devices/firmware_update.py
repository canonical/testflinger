"""Detecting device types"""

import subprocess
import logging
import json
from testflinger_device_connectors.fw_devices.dmi import Dmi
from testflinger_device_connectors.fw_devices import (
    AbstractDevice,
    LVFSDevice,
    OEMDevice,
)
from testflinger_device_connectors import logmsg


SSH_OPTS = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"


def all_subclasses(cls):
    return cls.__subclasses__() + [
        g for s in cls.__subclasses__() for g in all_subclasses(s)
    ]


def detect_device(ip: str, user: str, config: dict) -> AbstractDevice:
    """
    Detect device's firmware upgrade type by checking on DMI data

    :param ip:        DUT IP
    :param user:      DUT user
    :return:          device class object
    :rtype:           an instance of a class that implements AbstractDevice
    """
    temp_device = LVFSDevice(ip, user)
    run_ssh = temp_device.run_cmd
    devices = all_subclasses(AbstractDevice)

    try:
        dmi_chassis_vendor = "sudo cat /sys/class/dmi/id/chassis_vendor"
        dmi_chassis_type = "sudo cat /sys/class/dmi/id/chassis_type"
        rc1, vendor_string, stderr1 = run_ssh(
            dmi_chassis_vendor, raise_stderr=False
        )
        rc2, type_string, stderr2 = run_ssh(
            dmi_chassis_type, raise_stderr=False
        )
    except subprocess.CalledProcessError as e:
        logmsg(logging.ERROR, e.output)
        raise RuntimeError(e.output)

    err_msg = ""
    if rc1 != 0:
        err_msg = vendor_string + stderr1 + "\n"
    if rc2 != 0:
        err_msg = err_msg + type_string + stderr2
    if err_msg:
        err_msg = (
            "Unable to detect device vendor/type due to lacking of dmi info.\n"
            + err_msg
        )
        logmsg(logging.ERROR, err_msg)
        raise RuntimeError(err_msg)

    type_index = int(type_string)
    upgrade_type = Dmi.chassis_types[type_index]
    err_msg = (
        f"DMI chassis_vendor: {vendor_string} "
        + f"chassis_type: {Dmi.chassis_names[type_index]} "
        + "is not in current support scope"
    )

    try:
        dev = [
            dev
            for dev in devices
            if dev.fw_update_type in upgrade_type
            and any(x == vendor_string for x in dev.vendor)
        ][0]
        logmsg(logging.INFO, f"{ip} is a {vendor_string} {dev.__name__}")
    except IndexError:
        logmsg(logging.ERROR, err_msg)
        raise RuntimeError(err_msg)

    if issubclass(dev, LVFSDevice):
        return dev(ip, user)
    elif issubclass(dev, OEMDevice):
        # get BMC info from MAAS
        try:
            cmd = [
                f"maas {config['maas_user']} "
                f"node power-parameters {config['node_id']}"
            ]
            out = subprocess.check_output(
                cmd,
                shell=True,
                universal_newlines=True,
            ).strip()
            bmc_info = json.loads(out)
            return dev(
                ip,
                user,
                bmc_info["power_address"],
                bmc_info["power_user"],
                bmc_info["power_pass"],
            )
        except KeyError:
            raise RuntimeError("MAAS info isn't provided in config file")
        except subprocess.CalledProcessError:
            msg = f"maas error running: {' '.join(cmd)}"
            logmsg(logging.ERROR, msg)
            raise RuntimeError(msg)
