# Testflinger Server

This is the development guide for Testflinger Server. To see more general
contribution and development recommendations, refer to the
[contribution guide](../CONTRIBUTING.md)

## Development/Demo environment

### Docker

Testflinger server can be deployed using Docker, and it makes a nice setup
for local development. There's a Dockerfile for building the container and
a `docker-compose.yml` which can be used as a basis for development purposes.
This will setup Testflinger running on port 5000, along with MongoDB and Vault.

To get this running on your system:

```shell
docker-compose up -d --build
```

If you want to manage client credentials in your local database, you can use
a purpose-built tool:

```shell
docker exec -it testflinger-server client_credentials_admin
```

Also, if you want to add some sample data to your local development environment,
there's another helper script:

```console
$ devel/create_sample_data.py -h

    usage: create_sample_data.py [-h] [-a AGENTS] [-j JOBS] [-q QUEUES] [-s SERVER]

    Create sample data for testing Testflinger

    options:
    -h, --help            show this help message and exit
    -a AGENTS, --agents AGENTS
                            Number of agents to create
    -j JOBS, --jobs JOBS  Number of jobs to create
    -q QUEUES, --queues QUEUES
                            Number of queues to create
    -s SERVER, --server SERVER
                            URL of testflinger server starting with 'http(s)://...' (must not be production server)
```

The defaults are intended to be used with a server running on
`http://localhost:5000` which is what will be deployed by default if you use
the docker-compose setup above. So if this is what you want, you can just
call it with no options.

For testing routes that require SSO, the above docker-compose file also includes a development setup by using a generic IdP provider. 
The following entry must be added to `/etc/hosts` to allow localhost to perform the callback redirection to `dex` container:

```
127.0.0.1 localhost dex
```

Users and OIDC values can be easily configured through `devel/dex-config.yaml`. 
For testing a sample user is already added with the following credentials:

```
email: testlinger@example.com
username: "testflinger-admin"
password: testflinger
```

### Multipass

There is a `testflinger.yaml` file under the `devel/` directory which can
be used with multipass to create a complete environment for demonstrating,
testing, and developing on all parts of testflinger. This environment is
self-contained, and automatically set up to point the command-line tools
at a server running within this container. It also includes a deployment of
MAAS with a pre-configured example node that runs in a VM, so you can use
this environment to run a full test job through the entire process, including
provisioning.

It is recommended to have at least 8GB of RAM free and 32GB of disk space for
creating this container.

To get this running, first install multipass:

```shell
sudo snap install multipass
```

Next run the following command (this will take a while):

```shell
cat devel/testflinger.yaml |multipass launch --name testflinger -c4 -m8GB -d32GB --timeout 600 focal --cloud-init -
```

Due to the complexity of the environment being setup, this command may
timeout rather than complete. If this happens the environment should
still reach the final state successfully, but you will need to wait a
few minutes before trying to connect.

To open a shell to the container, run:

```shell
multipass exec testflinger bash
```

From there, you can look at the README file for more information

### Connect to MAAS with a web browser (Optional)

If you wish to connect to the Web UI for MAAS to watch or debug deployment
of the test container, you can get the ip address of the container using
'multipass list' and open a browser on your host system to:

```shell
http://<MAAS_IP>:5240/MAAS
```

### Cleanup and Removal

To remove everything that has been deployed completely:

```shell
multipass delete -p testflinger
```
