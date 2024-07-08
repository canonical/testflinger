# Zapper KVM

Zapper-driven provisioning method that makes use of KVM assertions and actions.


## Autoinstall based

Support for vanilla Ubuntu is provided by [autoinstall](https://canonical-subiquity.readthedocs-hosted.com/en/latest/intro-to-autoinstall.html). Supported Ubuntu versions are:

- Core24
- Desktop >= 23.04
- Server >= 20.04

Unless specified via _autoinstall_ storage filter, the tool will select the largest storage device on the DUT. See [supported layouts](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html#supported-layouts) for more information.

### Job parameters

- __url__: URL to the image to install
- __username__: username to configure
- __password__: password to configure
- **storage_layout**: can be either `lvm`, `direct`, `zfs` or `hybrid` (Core, Desktop 23.10+)
- **robot_tasks**: list of Zapper Robot tasks to run after a hard reset in order to follow the `autoinstall` installation
- **cmdline_append** (optional): kernel parameters to append at the end of GRUB entry cmdline
- **base_user_data** (optional): a custom base user-data file, it should be validated against [this schema](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-schema.html)

## Ubuntu Desktop OEM

### Jammy

Ubuntu OEM 22.04 is a two step process:

1. Install using Zapper automations the `alloem` image which creates the reset partition on DUT and installs Ubuntu Jammy
2. If URL is provided, run the OEM script to install an updated image on top of (1)

The tool will select the storage device with the following priority:

1. RAID
2. NVME
3. SATA

#### Job parameters

- __alloem_url__: URL to the `alloem` image
- __url__ (optional): URL to the image to test, will be installed via the OEM script
- __password__: password to configure
- **robot_tasks**: list of Zapper Robot tasks to run after a hard reset in order to follow the `alloem` installation

### Noble

Ubuntu OEM 24.04 uses `autoinstall`. The procedure and the arguments are the same as _vanilla_ Ubuntu.

## Live ISO

Support for live ISOs is simply performed booting from an external storage device and returning.

### Job parameters

- __boot_from_ext_media__: should be set to "true"
- __wait_until_ssh__: SSH assertion at the end of provisioning can be skipped, in case the live ISO does not include an SSH server

