:relatedlinks: [Ubuntu&#32;Security&#32;reporting&#32;and&#32;disclosure&#32;policy](https://ubuntu.com/security/disclosure-policy)

.. _security_overview:

Security Overview
=================

This document provides an overview of the security aspects of Testflinger,
including potential risks and the information security measures in place to protect
sensitive data.

Risks
-----

The main risks associated with Testflinger are related to credentials and data exposure.

Authentication credentials (``client_id`` and ``secret_key``) may be stored in
plain text in a ``.env`` file or in the local CLI configuration file. Users should
ensure these files are not committed to version control and that access to them is
restricted to the appropriate users. See
:doc:`Authentication using Testflinger CLI <../how-to/authentication>` for details
on how to configure credentials for CLI usage.

Job payloads submitted to the Testflinger server and job output logs may contain
sensitive information especially during the test data and test execution phase. 
Users should be mindful of what they include in jobs and should store sensitive data 
as ``secrets`` to ensure data is not exposed in logs or job definitions. 
See :doc:`Use Secrets how-to guide <../how-to/use-secrets>` for more information 
on how to store your ``secrets`` in Testflinger and how to use them in jobs.


Isolation and Confinement
-------------------------

Testflinger CLI is the main client for interacting with the Testflinger server.
It is distributed as a snap and confined using `AppArmor`_, which restricts the client's
access to only the necessary system resources and file access required for it to function.

The ``testflinger-cli`` `snap`_ is packaged with strict confinement and has a limited set
of interfaces required for network access and reading the home directory.


Cryptography
------------

All data exchanged with the Testflinger server is transmitted securely using
:abbr:`TLS (Transport Layer Security)`, ensuring that the data is protected
during transit.

Security reference information
------------------------------

For configuration options with security implications, refer to the
:doc:`CLI configuration reference <../reference/cli-config>` and the
:doc:`Testflinger server configuration reference <../reference/testflinger-server-conf>`.

Additionally, for reference on Testflinger secrets, please refer to the 
:doc:`Secrets reference <../reference/secrets>`.

Security Reporting and Disclosure
---------------------------------

Please refer to the `Security Policy`_ in the `canonical/testflinger`_
repository for details on reporting security issues.

The Ubuntu `Security reporting and disclosure policy`_ contains more information
about what you can expect when you contact us and what we expect from you.