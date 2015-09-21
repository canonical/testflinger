Snappy Device Agents
####################

Device agents scripts for provisioning and running tests on Snappy
devices

Supported Devices
=================

BeagleBone Black
----------------

To use snappy-device-agent with a BeagleBone, you will need to first
replace the image on emmc with a customized one.  The installer image
can be downloaded from::

    http://people.canonical.com/~plars/snappy/

Next, create a config file to give it some hints about your environment.
The config file for BeagleBone needs to have the address (host or ip) of
you test system once it boots, a list of commands to force it to boot the
master (emmc) image, a list of commands to force it to boot the test (snappy)
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

Raspberry Pi 2
--------------
Using the provisioning kit with Raspberry Pi 2 is similar to the Beaglebone.
The rpi2 will need to have a USB stick inserted for the test image, and the
SD card should boot the raspberry pi image from::

    http://people.canonical.com/~plars/snappy/

The snappy-device-agent script should just be called with the rpi2
subcommand instead of bbb.

Also, the default.yaml file passed to snappy-device-agent should include::

    test_device: /dev/sda

x86-64 Baremetal
----------------

The x86 baremetal device is currently supported using a process called inception. We boot from an ubuntu-server install running on a usb stick by default, then modify the grub entry on the host to add a boot entry for snappy on the hard drive.

The boot entry looks like this::

    # LAAS Inception Marker (do not remove)
    menuentry "LAAS Inception Test Boot (one time)" {
    insmod chain
    set root=hd1
    chainloader +1
    }
    # Boot into LAAS Inception OS if requested
    if [ "${laas_inception}" ] ; then
    set fallback="${default}"
    set default="LAAS Inception Test Boot (one time)"
    set laas_inception=
    save_env laas_inception
    set boot_once=true
    fi

To boot into this instance, you simply set the laas_inception grub variable to 1, and it will boot once into the install from the primary hard drive::

    $ sudo grub-editenv /boot/grub/grubenv set laas_inception=1

Because we install to the hard drive, and not a mmc with a known location, you should also specify the test device. Here is a complete example of a config yaml file::

    device_ip: 10.101.48.47
    test_device: /dev/sda
    select_master_script: []
    select_test_script:
        - ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null 10.101.48.47 sudo grub-editenv /boot/grub/grubenv set laas_inception=1
    reboot_script:
        - snmpset -c private -v1 pdu11.cert-maas.taipei .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.6 i 2
        - sleep 10
        - snmpset -c private -v1 pdu11.cert-maas.taipei .1.3.6.1.4.1.318.1.1.12.3.3.1.1.4.6 i 1


Logstash Logging
================

Log messages can optionally be directed to a logstash server by adding
two additional values in the yaml file::

    logstash_host: 10.0.3.207
    agent_name: test001

Logstash_host is the logstash server the messages will be sent to on port 5959.
Agent_name should be the name of the device this agent represents. It
will be added as extra data in the log message.
