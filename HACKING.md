# Running tests

To run the unit tests, install tox (this can be on your native system, via
pip, or in a virtual environment), and just run **tox**.

# Development/Demo environment

## Multipass

There is a **testflinger.yaml** file under the **devel** directory which can
be used with multipass to create a complete environment for demonstrating,
testing, and developing on all parts of testflinger. This environment is
self-contained, and automatically set up to point the command-line tools
at a server running within this container. It also includes a deployment of
MaaS with a pre-configured example node that runs in a VM, so you can use
this environment to run a full test job through the entire process, including
provisioning.

It is recommended to have at least 8GB of RAM free and 32GB of disk space for
creating this container.

To get this running, first install multipass:
```
    $ sudo snap install multipass
```

Next run the following command (this will take a while):
```
    $ cat devel/testflinger.yaml |multipass launch --name testflinger -c4 -m8GB -d32GB --timeout 600 --cloud-init -
```

Due to the complexity of the environment being setup, this command may
timeout rather than complete. If this happens the environment should
still reach the final state successfully, but you will need to wait a
few minutes before trying to connect.

To open a shell to the container, run:
```
    $ multipass exec testflinger bash
```

From there, you can look at the README file for more information

### Connect to MAAS with a web browser (Optional)

If you wish to connect to the Web UI for MAAS to watch or debug deployment
of the test container, you can get the ip address of the container using
'multipass list' and open a browser on your host system to:
```
    http://<MAAS_IP>:5240/MAAS    
```

### Cleanup and Removal

To remove everything that has been deployed completely:
```
    $ multipass delete -p testflinger
```
