# Zapper KVM

Zapper-driven provisioning method that makes use of KVM assertions and actions.


## Autoinstall based

Support for vanilla Ubuntu is provided by [autoinstall](https://canonical-subiquity.readthedocs-hosted.com/en/latest/intro-to-autoinstall.html). Supported Ubuntu versions are:

- Desktop >= 23.04
- Server >= 20.04
- UC24 (experimental)

Unless specified via _autoinstall_ storage filter, the tool will select the largest storage device on the DUT. See [supported layouts](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html#supported-layouts) for more information.

### Job parameters

- __url__: URL to the image to install
- __username__: username to configure
- __password__: password to configure
- __storage_layout__: can be either `lvm`, `direct`, `zfs` or `hybrid` (Desktop 23.10+, UC24)
- __robot_tasks__: list of Zapper Robot tasks to run after a hard reset in order to follow the `autoinstall` installation
- __cmdline_append__ (optional): kernel parameters to append at the end of GRUB entry cmdline
- __base_user_data__ (optional): a string containing base64 encoded autoinstall user-data to use as base for provisioning, it should be validated against [this schema](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-schema.html)
- __autoinstall_oem__: (optional): set to "true" to install OEM meta-packages and the reset partition (Desktop 24.04+)

## Ubuntu Desktop 22.04 OEM

Ubuntu OEM 22.04 is a two step process:

1. Install using Zapper automations the `alloem` image which creates the reset partition on DUT and installs Ubuntu Jammy
2. If URL is provided, run the OEM script to install an updated image on top of (1)

The tool will select the storage device with the following priority:

1. RAID
2. NVME
3. SATA

### Job parameters

- __alloem_url__: URL to the `alloem` image
- __url__ (optional): URL to the image to test, will be installed via the OEM script
- __password__: password to configure
- __robot_tasks__: list of Zapper Robot tasks to run after a hard reset in order to follow the `alloem` installation

## Live ISO

Support for live ISOs is simply performed booting from an external storage device and returning right after KVM interactions.

### Job parameters

- __live_image__: Set to "true" to ensure that the Zapper considers the provision process complete at the end of KVM interactions defined by the specified `robot_tasks`, without needing to unplug the external media.
- __wait_until_ssh__: If set to "false", the Zapper will skip the SSH connection attempt, which is normally performed at the end of provisioning as a form of boot assertion. This is primarily useful in cases where the live ISO does not include an SSH server.

