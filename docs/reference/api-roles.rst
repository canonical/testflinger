.. _api-roles:

API endpoint roles
==================

The table below lists every Testflinger server endpoint together with the roles
that are permitted to call it.  The four roles are:

``AGENT``
    Credentials issued to a Testflinger agent host.  Used for machine-to-machine
    communication between the agent and the server.

``CONTRIBUTOR``
    The default role assigned to human users.  Grants access to job submission,
    result retrieval, queue inspection, secret management, and read access to
    restricted-queue information.

    .. note::

       When OIDC is **not** enabled on the server, ``CONTRIBUTOR`` endpoints
       also accept anonymous (unauthenticated) connections.  This means any
       client can reach those endpoints without providing credentials.  Once
       OIDC is enabled, a valid token is required.

``MANAGER``
    A superset of ``CONTRIBUTOR`` that additionally covers client-permission
    management, restricted-queue ownership management, and agent management
    (reading and writing agent data, images, and queues).  It does **not**
    include the runtime agent operations reserved for the ``AGENT`` role
    (job consuming, posting provision logs, posting status events, fetching
    job attachments, and posting results, artifacts, and log fragments).

``ADMIN``
    Full access to all endpoints, including user/credential administration.

Endpoints that require no authentication 
------------------------------------------

.. list-table:: Endpoints that require no authentication
   :header-rows: 1
   :widths: 8 36 56

   * - Method
     - URI
     - Notes
   * - ``GET``
     - ``/v1/``
     - Server identification endpoint.  Always accessible without
       authentication.
   * - ``GET``
     - ``/metrics``
     - Prometheus metrics endpoint.  Always accessible without
       authentication on metrics port, default 9090.
   * - ``POST``
     - ``/oidc/auth-init``
     - Initiates the OIDC device-flow authentication with the provider.
       Cannot require authentication because this is how a client
       *obtains* credentials.
   * - ``POST``
     - ``/oidc/auth-poll/{request_id}``
     - Polls for the OIDC authentication result.  Cannot require
       authentication for the same reason as ``/oidc/auth-init``.
   * - ``POST``
     - ``/v1/oauth2/token``
     - Exchanges client credentials (HTTP Basic) for a JWT access token
       and a refresh token.  Cannot require a Bearer token because this
       is how a client *obtains* one.
   * - ``POST``
     - ``/v1/oauth2/refresh``
     - Exchanges a valid refresh token for a new access token.  No
       Bearer token is required; the refresh token itself is the
       credential.

Endpoint permissions by role
----------------------------

.. include:: api-roles-table.txt
