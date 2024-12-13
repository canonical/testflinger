Testflinger Device Connectors
####################

Device connectors scripts for provisioning and running tests on Testflinger
devices

Supported Devices
=================

The following device connector types are currently supported, however most of them
require a very specific environment in order to work properly. That's part of
the reason why they are broken out into a separate project. Nothing here is
really required to run testflinger, only to support these devices in our
environment. Alternative device connectors could be written in order to support
testing on other types of devices.

- cm3 - Raspberry PI CM3 with a sidecar device and tools to support putting it in otg mode to flash an image
- dragonboard - dragonboard with a stable image on usb and test images are flashed to a wiped sd with a dual boot process
- fake_connector - fake device connector that can be used for testing
- maas2 - Metal as a Service (MAAS) systems, which support additional features such as disk layouts. Images provisioned must be imported first!
- multi - multi-device connector used for provisioning jobs that span multiple devices at once
- muxpi - muxpi/sdwire provisioned devices that utilize a device that can write to an sd the boot it on the DUT
- netboot - minimal netboot initramfs process for a specific device that couldn't be provisioned with MAAS
- noprovision - devices which need to run tests, but can't be provisioned (yet)
- oemrecovery - anything (such as core fde images) that can't be provisioned but can run a set of commands to recover back to the initial state
- oemscript - uses a script that supports some oem images and allows injection of an iso to the recovery partition to install that image


Exit Status
===========

Device connectors will exit with a value of ''46'' if something goes wrong during
device recovery. This can be used as an indication that the device is unusable
for some reason, and can't be recovere using automated recovery mechanisms.
The system calling the device connector may want to take further action, such
as alerting someone that it needs manual recovery, or to stop attempting to
run tests on it until it's fixed.
