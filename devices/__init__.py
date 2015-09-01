# Copyright (C) 2015 Canonical
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import imp
import os


class ProvisioningError(Exception):
    pass


class RecoveryError(Exception):
    pass


def load_devices():
    devices = []
    device_path = os.path.dirname(os.path.realpath(__file__))
    devs = [os.path.join(device_path, device)
            for device in os.listdir(device_path)
            if os.path.isdir(os.path.join(device_path, device))]
    for device in devs:
        if '__pycache__' in device:
            continue
        module = imp.load_source(
            'module', os.path.join(device, '__init__.py'))
        devices.append((module.device_name, module.DeviceAgent))
    return tuple(devices)

if __name__ == '__main__':
    load_devices()
