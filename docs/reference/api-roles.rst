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

.. rst-class:: api-roles-table

.. list-table:: Endpoint permissions by role
   :header-rows: 1
   :widths: 8 36 10 13 10 8

   * - Method
     - URI
     - AGENT
     - CONTRIBUTOR
     - MANAGER
     - ADMIN
   * - ``POST``
     - ``/v1/agents/provision_logs/{agent_name}``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
   * - ``GET``
     - ``/v1/job``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
   * - ``GET``
     - ``/v1/job/{job_id}/attachments``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
   * - ``POST``
     - ``/v1/job/{job_id}/events``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
   * - ``POST``
     - ``/v1/result/{job_id}``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
   * - ``POST``
     - ``/v1/result/{job_id}/artifact``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
   * - ``POST``
     - ``/v1/result/{job_id}/log/{log_type}``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
   * - ``POST``
     - ``/v1/agents/data/{agent_name}``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``POST``
     - ``/v1/agents/images``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``POST``
     - ``/v1/agents/queues``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/agents/data/{agent_name}``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/result/{job_id}``
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/agents/data``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/agents/images/{queue}``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/agents/queues``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/queues/{queue_name}/agents``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/queues/{queue_name}/jobs``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/queues/wait_times``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``POST``
     - ``/v1/job``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/job/{job_id}``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``POST``
     - ``/v1/job/{job_id}/action``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``POST``
     - ``/v1/job/{job_id}/attachments``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/job/{job_id}/position``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/job/search``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/result/{job_id}/artifact``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/result/{job_id}/log/{log_type}``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``DELETE``
     - ``/v1/secrets/{client_id}/{path}``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``PUT``
     - ``/v1/secrets/{client_id}/{path}``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/restricted-queues``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/restricted-queues/{queue_name}``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/client-permissions/{client_id}``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``GET``
     - ``/v1/client-permissions``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``PUT``
     - ``/v1/client-permissions/{client_id}``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``DELETE``
     - ``/v1/restricted-queues/{queue_name}``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``POST``
     - ``/v1/restricted-queues/{queue_name}``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``DELETE``
     - ``/v1/client-permissions/{client_id}``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
   * - ``POST``
     - ``/v1/oauth2/revoke``
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`x-circle-fill;1em;sd-text-danger` :vh:`restricted`
     - :octicon:`check-circle-fill;1em;sd-text-success` :vh:`allowed`
