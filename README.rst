Snappy Device Agents
####################

Device agents scripts for provisioning and running tests on Snappy
devices

Supported Devices
=================

Only BeagleBone Black is supported for the moment, and for provisioning
to work properly, things have to be set up in a very specific way.  Once
we have devices in the lab, this will be made a little more generic, but
will probably always require specialized hardware to be fully automated.

BeagleBone Black
----------------

To use snappy-device-agent with a BeagleBone, you will need to create a
config file to give it some hints about your environment. The config
file for BeagleBone needs to have the address (host or ip) of you test
system once it boots, a list of commands to force it to boot the master
(emmc) image, a list of commands to force it to boot the test (snappy)
image, and a list of commands to force a hard poweroff/poweron.

If you have a very simple setup, these command scripts could be as
simple as a script to run over ssh. In a production environment, it
could be calling a REST API to trigger a relay and force these things.
Different devices can even use different config files. The config file
gives you the flexibility to define what works for this particular device.

Example::

    device_ip: 192.168.1.147
    select_master_script:
        - ssh pi@192.168.1.136 bin/setboot master
    select_test_script:
        - ssh pi@192.168.1.136 bin/setboot test
    reboot_script:
        - ssh pi@192.168.1.136 bin/hardreset
