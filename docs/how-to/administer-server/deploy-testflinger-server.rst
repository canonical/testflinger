.. _howto-deploy-server:

Deploy a Testflinger Server
===========================

This guide outlines the steps to deploy a Testflinger server using Juju and
the Testflinger server charm from Charmhub.

Testflinger server runs as a Kubernetes application and uses MongoDB as its
backend. In this guide, MongoDB is deployed as a machine charm and connected
to the server through a Juju cross-model relation. For more details, see the 
:doc:`../../explanation/architecture` explanation.

Prerequisites
-------------

The following prerequisites cover the necessary steps to set up K8s and
machine-based Juju environments required for the Testflinger server
deployment. For a detailed guide on how to set up Juju, refer to the
`official Juju documentation <https://documentation.ubuntu.com/juju/>`_.

Dependencies
^^^^^^^^^^^^

Install the following dependencies:

.. code-block:: shell

  $ sudo apt-get install git
  $ sudo snap install juju lxd
  $ sudo snap install microk8s --channel <latest_version>-strict
  $ sudo snap install terraform --classic

.. note::

   Juju 3.x requires the strict version of the ``microk8s`` snap to be installed.

LXD
^^^

Make sure LXD is initialized.

.. code-block:: shell

  $ lxd init --auto

.. note::

  Feel free to initialize LXD with a configuration that suits your needs. 
  LXD is only used in this setup to deploy the machine charms, specifically
  the MongoDB machine charm.


MicroK8s
^^^^^^^^

The Testflinger server deployment depends on the following MicroK8s setup.

.. code-block:: shell

  $ sudo snap alias microk8s.kubectl kubectl
  $ sudo usermod -aG snap_microk8s ubuntu
  $ newgrp snap_microk8s  # or reboot
  $ microk8s status --wait-ready
  $ sudo microk8s enable dns hostpath-storage ingress

Juju
^^^^

Set up the Juju controllers needed for the Testflinger server deployment.

.. code-block:: shell

  $ juju bootstrap localhost localhost-controller
  $ microk8s config | juju add-k8s localhost-microk8s --controller localhost-controller

Then create the models for the server and database deployments.

.. code-block:: shell

  $ juju add-model testflinger-db localhost
  $ juju add-model testflinger localhost-microk8s

MongoDB deployment
------------------

Deploy the MongoDB charm into the ``testflinger-db`` model.

.. code-block:: shell

  $ juju deploy mongodb --channel 6/stable -m testflinger-db

Once the deployment is complete, offer the MongoDB endpoint so that it can
be consumed by the Testflinger server application in the K8s model.
For more information on how to use Juju ``offer``, please refer to the 
`Juju offer CLI reference <Juju Offer_>`_.

.. code-block:: shell

  $ juju offer testflinger-db.mongodb:database mongodb

Testflinger server deployment
------------------------------

.. tip::

  The next steps assume you are located in the k8s model, otherwise you can
  switch by running ``juju switch testflinger``.

Juju CLI
^^^^^^^^

The following steps outline how to deploy the Testflinger server charm
using the Juju CLI.

First, consume the MongoDB endpoint offered in the previous step. For 
more information on how to use Juju ``consume``, please refer to the 
`Juju consume CLI reference <Juju Consume_>`_.

.. code-block:: shell

  $ juju consume localhost-controller:admin/testflinger-db.mongodb

Deploy the Testflinger server charm.

.. code-block:: shell

  $ juju deploy testflinger-k8s --channel stable \
      --config jwt_signing_key="<signing-key>"

.. note::

  The ``jwt_signing_key`` configuration is required for authenticating
  API requests to the Testflinger server. You should generate a secure
  random string to use as the signing key.

.. note::

  You can also pass the ``-n <units>`` flag to deploy multiple units of the
  Testflinger server application. Adjust this number based on your needs
  and the resources available in your cluster.

Relate the Testflinger server application with the MongoDB endpoint.

.. code-block:: shell

  $ juju integrate testflinger-k8s:mongodb_client mongodb:database

Monitor the deployment progress until all units are active.

.. code-block:: shell

  $ juju status --storage --relations --watch 5s

Once all units are active, deploy and configure the ingress charm to
expose the Testflinger server API. In this example, we will use the
NGINX Ingress Integrator charm. 

.. code-block:: shell

  $ juju deploy nginx-ingress-integrator --trust
  $ juju integrate nginx-ingress-integrator testflinger-k8s
  $ juju config testflinger-k8s external_hostname=testflinger.local

The deployment finishes when the status shows ``Ingress IP(s): 127.0.0.1``
on ``nginx-ingress-integrator``. The IP addresses may differ based on your
Kubernetes cluster setup. You can run the `juju status` command to 
monitor the status of the deployment and check the assigned ingress IP address.

.. code-block:: shell

  $ juju status --storage --relations
    Model        Controller            Cloud/Region                  Version  SLA          Timestamp
    testflinger  localhost-controller  localhost-microk8s/localhost  3.6.21   unsupported  11:49:45-06:00

    SAAS     Status  Store                 URL
    mongodb  active  localhost-controller  admin/testflinger-db.mongodb

    App                       Version  Status  Scale  Charm                     Channel        Rev  Address        Exposed  Message
    nginx-ingress-integrator  24.2.0   active      1  nginx-ingress-integrator  latest/stable  203  10.152.183.35  no       Ingress IP(s): 127.0.0.1
    testflinger-k8s           ...      active      1  testflinger-k8s           latest/stable  288  10.152.183.88  no       

    Unit                         Workload  Agent  Address       Ports  Message
    nginx-ingress-integrator/0*  active    idle   10.1.153.199         Ingress IP(s): 127.0.0.1
    testflinger-k8s/0*           active    idle   10.1.153.198         

    Integration provider                  Requirer                              Interface       Type     Message
    mongodb:database                      testflinger-k8s:mongodb_client        mongodb_client  regular  
    nginx-ingress-integrator:nginx-peers  nginx-ingress-integrator:nginx-peers  nginx-instance  peer     
    nginx-ingress-integrator:nginx-route  testflinger-k8s:nginx-route           nginx-route     regular  

.. warning::

  The above ingress deployment steps are intended for testing and
  development purposes. For production deployments, it is recommended to
  use TLS for secure communication. For more information on how to set
  up TLS, refer to the
  `NGINX Ingress Integrator charm documentation <nginx-ingress-tls_>`_.

Terraform
^^^^^^^^^

Testflinger also provides a Terraform module that automates the deployment
of the Testflinger server. The module is located in the
`server/terraform/ <testflinger-terraform_>`_ directory of the Testflinger
repository.

.. important::

  The Terraform module will only deploy the Testflinger server charm, it is
  user responsibility to set up a Terraform plan that deploys the Ingress charm
  and configures the required relations. For a sample Terraform plan, 
  please refer to the `server/terraform/dev/main.tf <testflinger-terraform-dev_>`_ 
  file in the Testflinger repository.

Variables
~~~~~~~~~

Create a ``terraform.tfvars`` file and define the following variables.

.. code-block:: text

  jwt_signing_key                = "(sensitive value)"
  external_hostname              = "testflinger.local"

.. note::

  Refer to ``server/terraform/variables.tf`` and
  ``server/terraform/README.md`` for the full list of available variables
  and their descriptions.

Apply the Terraform plan
~~~~~~~~~~~~~~~~~~~~~~~~

Initialize Terraform and apply the plan.

.. code-block:: shell

  $ terraform init
  $ terraform apply  # optionally run 'terraform plan' first

Wait for the Juju units to finish their setup.

.. code-block:: shell

  $ juju status --storage --relations --watch 5s

Networking
----------

Ensure that your system can resolve and reach the ``external_hostname``
configured earlier. For local testing, edit ``/etc/hosts`` to define
the name resolution.

.. code-block:: text

  127.0.0.1  testflinger.local

Testflinger CLI
---------------

Testflinger CLI defaults to using ``testflinger.canonical.com`` as its
Testflinger server. To override the server being used, pass the
``--server`` flag or edit the ``testflinger-cli.conf`` configuration file.

First, install Testflinger CLI.

.. code-block:: shell

  $ sudo snap install testflinger-cli

Then connect to the server.

.. code-block:: shell

  $ testflinger-cli --server http://testflinger.local list-agents

The CLI should not error out, though the list of agents may be empty.

Refer to the :doc:`/reference/cli-config` reference for details on
configuring the CLI.

.. _Juju Consume: https://documentation.ubuntu.com/juju/3.6/reference/juju-cli/list-of-juju-cli-commands/consume/
.. _Juju Offer: https://documentation.ubuntu.com/juju/3.6/reference/juju-cli/list-of-juju-cli-commands/offer/
.. _nginx-ingress-tls: https://documentation.ubuntu.com/nginx-ingress-integrator-charm/latest/how-to/secure-an-ingress-with-tls/
.. _testflinger-terraform: https://github.com/canonical/testflinger/tree/main/server/terraform
.. _testflinger-terraform-dev: https://github.com/canonical/testflinger/blob/main/server/terraform/dev/main.tf