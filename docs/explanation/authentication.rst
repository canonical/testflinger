.. _authentication:

Authentication and Authorisation
================================

Authentication
--------------

Testflinger can be configured to use OpenID Connect (OIDC) for authentication. The way that
authorization working in the Testflinger server depends on whether OIDC is enabled or not. When
OIDC is *not* enabled, Testflinger supports anonymous logins. However, when OIDC is enabled
each request must be authenticated. Both operating modes support use of self-signed tokens
for authentication, and these are what are used in typical CI/CD flows.

Since Basic Auth can be used in both configurations, it is prioritized and will be handled within the server before other authentication methods.

Authentication Flows
--------------------

The following sequence diagrams show the authentication flow for each of the
authentication methods and the interactions between the user, the CLI and the
server.

.. note::

    For simplicity, all of the diagrams are targetting the ``/v1/jobs`` endpoint
    on Testflinger server side but the same flow applies to any other endpoint
    that requires authentication.

The Testflinger server can be configured one of two ways:
 - Without OIDC Authentication Configured (OIDC Disabled)
 - With OIDC Authentication Configured (OIDC Enabled)


OIDC Disabled
~~~~~~~~~~~~~

When Testflinger is configured to *not* use OIDC for authentication, the order is:

1. Basic Auth using ``client_id`` and ``secret_key``
2. Bearer token using a refresh token
3. Any non-authenticated requests are treated as an anonymous CONTRIBUTOR role.

.. _basic-auth-is-oidc-agnostic:

Basic Auth
''''''''''

Regardless of whether OIDC is enabled or not, Basic Auth will be used if both the
``client_id`` and ``secret_key`` are provided.

.. mermaid::
    :alt: Sequence diagram showing Basic Auth is used when client_id and secret_key are provided
    :caption: Sequence diagram showing Basic Auth is used when client_id and secret_key are provided
    :align: center

    sequenceDiagram
        actor User
        participant CLI as testflinger-cli
        participant Server as testflinger-server

        Note over User,Server: Have client-id + secret-key, use basic auth
        User->>CLI: Run command with client-id + secret-key
        CLI->>CLI: Validate both parameters are present
        CLI->>Server: Request with Basic Auth<br/>base64(client-id:secret-key)
        Note over CLI,Server: POST /v1/oauth2/token
        Server->>Server: Validate client credentials
        Server-->>CLI: 200 OK / return access and refresh tokens
        CLI-->>Server: use access token to complete the request
        Note over CLI,Server: POST /v1/jobs
        Server->>Server: Validate access token signature and client permissions
        Server-->>CLI: 200 OK / authenticated response
        CLI-->>User: Show result

Since ``client_id`` and ``secret_key`` are given explicit priority, if one of
them is missing, the request will not be sent to the server and the user will
be prompted to provide both parameters.

.. mermaid::
    :alt: The CLI will reject the call as an invalid combination, nothing will be sent to the server
    :caption: The CLI will reject the call as an invalid combination, nothing will be sent to the server
    :align: center

    sequenceDiagram
        actor User
        participant CLI as testflinger-cli

        Note over User,CLI: One of client-id or secret-key is missing
        User->>CLI: Run command with wrong number of credential arguments
        CLI-->>User: Show usage

.. _refresh-auth-is-oidc-agnostic:

Refresh Token
'''''''''''''

If client credentials are not provided, the CLI will attempt to use a refresh
token if one is available. The refresh token is stored in a snap-local cache and is
used to obtain a new access token for the user. The refresh token is valid for 6 days,
after which it will expire and the user will need to re-authenticate.

When a valid refresh token is present, this flow applies regardless of whether
OIDC is enabled on the server:

.. mermaid::
    :alt: Sequence diagram showing a refresh token being used and accepted
    :caption: Sequence diagram showing a refresh token being used and accepted
    :align: center

    sequenceDiagram
        actor User
        participant CLI as testflinger-cli
        participant Server as testflinger-server

        Note over User,Server: Neither client-id nor secret-key, refresh token accepted
        User->>CLI: Run command without client-id + secret-key
        CLI->>CLI: Load stored refresh token
        CLI->>Server: Request with refresh token
        Note over CLI,Server: POST /v1/oauth2/refresh
        Server->>Server: Validate token
        Server-->>CLI: 200 OK / return access and refresh tokens
        CLI-->>Server: use access token to complete the request
        Note over CLI,Server: POST /v1/jobs
        Server->>Server: Validate access token signature and client permissions
        Server-->>CLI: 200 OK / authenticated response
        CLI-->>User: Show result

Token expired or rejected
.........................

The server returns a 401 and the CLI removes the stored token. If the CLI does not
automatically retry the operation anonymously it will signal to the user that the
request was denied so the user may try again.

.. mermaid::
    :alt: Sequence diagram showing a refresh token being rejected and the user being denied access
    :caption: Sequence diagram showing a refresh token being rejected and the user being denied access
    :align: center

    sequenceDiagram
        actor User
        participant CLI as testflinger-cli
        participant Server as testflinger-server

        Note over User,Server: Neither client-id nor secret-key, token rejected, server does not use OIDC
        User->>CLI: Run command without client-id + secret-key
        CLI->>CLI: Load stored refresh token
        CLI->>Server: Request with refresh token
        Note over CLI,Server: POST /v1/oauth2/refresh
        Server->>Server: Token expired or rejected
        Server-->>CLI: 400 Bad Request
        CLI->>CLI: Delete stored refresh token
        CLI-->>User: Authentication failed

No credentials or stored token
''''''''''''''''''''''''''''''

If the server does not require authentication, the request is allowed through
as an anonymous user:

.. mermaid::
    :alt: Sequence diagram showing no auth for anonymous login
    :caption: Sequence diagram showing no auth for anonymous login
    :align: center

    sequenceDiagram
        actor User
        participant CLI as testflinger-cli
        participant Server as testflinger-server

        Note over User,Server: Neither client-id nor secret-key, no token, server does not require auth
        User->>CLI: Run command without credentials or token
        CLI->>CLI: No stored bearer/refresh token found
        CLI->>Server: Request without Authorization header
        Note over CLI,Server: POST /v1/jobs
        Server->>Server: Auth not required
        Server-->>CLI: 200 OK / anonymous user response
        CLI-->>User: Show result

OIDC Enabled
~~~~~~~~~~~~

When Testflinger is configured to use OpenID Connect (OIDC) for authentication, the order is:

1. Basic Auth using ``client_id`` and ``secret_key``
2. Bearer token using a refresh token
3. OIDC authentication flow

Basic Auth
''''''''''

Exactly the same as without OIDC, see :ref:`basic-auth-is-oidc-agnostic`.

Refresh Token
'''''''''''''

Exactly the same as without OIDC, see :ref:`refresh-auth-is-oidc-agnostic`.

Token expired or rejected
.........................

If the server has OIDC enabled and the refresh token is rejected, the server
initiates an OIDC authentication flow:

.. mermaid::
    :alt: Sequence diagram showing a refresh token being rejected and the server initiating OIDC process
    :caption: Sequence diagram showing a refresh token being rejected and the server initiating OIDC process
    :align: center

    sequenceDiagram
        actor User
        participant CLI as testflinger-cli
        participant Server as testflinger-server
        participant OIDC as OIDC provider

        Note over User,OIDC: Neither client-id nor secret-key, token rejected, server uses OIDC
        User->>CLI: Run command without client-id + secret-key
        CLI->>CLI: Load stored refresh token
        CLI->>Server: Request with refresh token
        Note over CLI,Server: POST /v1/oauth2/refresh
        Server->>Server: Token expired or rejected
        Server-->>CLI: 400 Bad Request
        CLI->>CLI: Delete stored refresh token
        CLI->>Server: Initiate OIDC auth flow
        Note over CLI,Server: POST /oidc/auth-init
        Server-->>OIDC: Proxy request to OIDC provider
        OIDC-->>Server: device_code + user_code + URL for OIDC handshake
        Server->>CLI: request_id + user code + URL for OIDC handshake
        CLI->>User: Display URL and code
        User->>OIDC: Complete the handshake
        CLI->>Server: Poll for auth completion
        Note over CLI,Server: POST /oidc/auth-poll/<request_id>
        Server-->>OIDC: Is this user cool?
        OIDC-->>Server: Yes + user identity (email)
        Server->>CLI: Issue refresh and access token
        CLI->>Server: Send request with access token
        Note over CLI,Server: POST /v1/jobs
        Server->>Server: Validate access token signature and client permissions
        Server-->>CLI: 200 OK / authenticated response
        CLI-->>User: Show result

No credentials or stored token
''''''''''''''''''''''''''''''

.. mermaid::
    :alt: Sequence diagram showing no stored token with OIDC enabled, triggering the OIDC flow
    :caption: Sequence diagram showing no stored token with OIDC enabled, triggering the OIDC flow
    :align: center

    sequenceDiagram
        actor User
        participant CLI as testflinger-cli
        participant Server as testflinger-server
        participant OIDC as OIDC provider

        Note over User,OIDC: Neither client-id nor secret-key, no token, server uses OIDC
        User->>CLI: Run command without credentials or token
        CLI->>CLI: No stored bearer/refresh token found
        CLI->>Server: Initiate OIDC auth flow
        Note over CLI,Server: POST /oidc/auth-init
        Server-->>OIDC: Proxy request to OIDC provider
        OIDC-->>Server: device_code + user_code + URL for OIDC handshake
        Server->>CLI: request_id + user code + URL for OIDC handshake
        CLI->>User: Display URL and code
        User->>OIDC: Complete the handshake
        CLI->>Server: Poll for auth completion
        Note over CLI,Server: POST /oidc/auth-poll/<request_id>
        Server-->>OIDC: Is this user cool?
        OIDC-->>Server: Yes + user identity (email)
        Server->>CLI: Issue refresh token and access token
        CLI->>Server: Send request with access token
        Note over CLI,Server: POST /v1/jobs
        Server->>Server: Validate access token signature and client permissions
        Server-->>CLI: 200 OK / authenticated response
        CLI-->>User: Show result

Authorisation
-------------

Once a client is authenticated, the server checks what actions that client is
allowed to perform. Authorisation is enforced on every request via the
permissions encoded in the client's access token.

Roles
~~~~~

Every authenticated client is assigned one of the following roles. Roles are
hierarchical: higher roles include all capabilities of lower ones.

.. list-table::
    :header-rows: 1
    :widths: 15 85

    * - Role
      - Capabilities
    * - ``admin``
      - Full access. Can manage all client permissions, revoke tokens,
        and administer restricted queues.
    * - ``manager``
      - Can read and write client permissions and manage restricted queues,
        but cannot delete clients or revoke tokens.
    * - ``contributor``
      - Can submit jobs with elevated priority, access restricted queues, and
        have extended reservation timeouts.
    * - ``agent``
      - Can fetch jobs from queues to execute. Only assigned to testflinger agents.

Job Submission Permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~

In addition to role-based access, per-client permissions can restrict job
submission further:

- :doc:`Restricted queues <restricted-queues>` — certain queues require explicit access. A client
  must be listed as an owner of a restricted queue before it can submit jobs
  to it.

- :doc:`Priority <job-priority>` — jobs can be submitted with a priority value to influence
  scheduling order. Each client has a ``max_priority`` limit per queue. 

- :doc:`Extended reservation <extended-reservation>` — authenticated users can reserve a device
  beyond the default 6-hour limit if permission is granted to specific queues.

.. note::

    Permissions and the role assigned to a client are managed by the server
    administrator. To request access, contact the administrator with the role
    you require and, if applicable, the additional permissions you need.
