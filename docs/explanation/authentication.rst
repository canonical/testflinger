.. _authentication:

Authentication and Authorisation
================================

Testflinger can be configured to use OpenID Connect (OIDC) for authentication.
Depending on whether the server is configured to use OIDC, the authentication flow will differ.

The following is the simplified priority order of authentication methods:

1. Basic Auth using ``client_id`` and ``secret_key``
2. Bearer token using a refresh token
3. OIDC flow if enabled on the server

Authentication Flows
--------------------

The following sequence diagrams show the authentication flow for each of the
authentication methods and the interactions between the user, the CLI and the
server.

Basic Auth
~~~~~~~~~~

Regardless of whether OIDC is enabled or not, Basic Auth will be used if both the
``client_id`` and ``secret_key`` are provided.

.. mermaid::
    :alt: Sequence diagram showing BASIC Auth is used when client_id and secret_key are provided
    :caption: Sequence diagram showing BASIC Auth is used when client_id and secret_key are provided
    :align: center

    sequenceDiagram
        actor User
        participant CLI as testflinger-cli
        participant Server as testflinger-server

        Note over User,Server: Have client-id + secret-key, use basic auth
        User->>CLI: Run command with client-id + secret-key
        CLI->>CLI: Validate both parameters are present
        CLI->>Server: Request with Basic Auth<br/>base64(client-id:secret-key)
        Server->>Server: Validate client credentials
        Server-->>CLI: 200 OK / return access and refresh tokens
        CLI-->>Server: use access token to complete the request
        Server->>Server: Validate client permissions
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


Refresh Token
~~~~~~~~~~~~~

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
        CLI->>CLI: Load stored refresh/bearer token
        CLI->>Server: Request with Bearer refresh token
        Server->>Server: Validate token
        Server-->>CLI: 200 OK / return access and refresh tokens
        CLI-->>Server: use access token to complete the request
        Server->>Server: Validate client permissions
        Server-->>CLI: 200 OK / authenticated response
        CLI-->>User: Show result

Token expired or rejected
.........................

When the refresh token is rejected, the behavior differs depending on whether
the server has OIDC enabled.

With OIDC Enabled
'''''''''''''''''''

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
        CLI->>CLI: Load stored refresh/bearer token
        CLI->>Server: Request with Bearer refresh token
        Server->>Server: Token expired or rejected
        Server-->>OIDC: Initiate OIDC auth flow
        OIDC-->>Server: Auth code
        Server->>CLI: 401 Unauthorized, try this instead: Auth code
        CLI->>CLI: Delete stored token
        CLI->>User: Display URL and code
        User->>OIDC: Complete the handshake
        CLI->>Server: Poll for auth completion
        Server-->>OIDC: Is this user cool?
        OIDC-->>Server: Yes + user identity (email)
        Server->>CLI: Issue refresh token
        CLI->>Server: Retry request with new Bearer token
        Server-->>CLI: 200 OK / authenticated response
        Server->>Server: Validate client permissions
        CLI-->>User: Show result

Without OIDC
''''''''''''

If the server does not have OIDC enabled and the refresh token is rejected,
the server returns a 401 and the CLI removes the stored token:

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
        CLI->>CLI: Load stored refresh/bearer token
        CLI->>Server: Request with Bearer refresh token
        Server->>Server: Token expired or rejected
        Server-->>CLI: 401 Unauthorized, delete stored token
        CLI->>CLI: Delete stored token
        CLI-->>User: Authentication failed

No credentials or stored token
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When neither credentials nor a stored token are available, the behavior
depends on whether the server has OIDC enabled.

If the server has OIDC enabled, it initiates an OIDC authentication flow:

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
        CLI->>Server: Request without Authorization header
        Server-->>OIDC: Initiate OIDC auth flow
        OIDC-->>Server: Auth code
        Server->>CLI: 401 Unauthorized, try this instead: Auth code
        CLI->>User: Display URL and code
        User->>OIDC: Complete the handshake
        CLI->>Server: Poll for auth completion
        Server-->>OIDC: Is this user cool?
        OIDC-->>Server: Yes + user identity (email)
        Server->>CLI: Issue refresh token
        CLI->>Server: Retry request with new Bearer token
        Server-->>CLI: 200 OK / authenticated response
        Server->>Server: Validate client permissions
        CLI-->>User: Show result

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
        Server->>Server: Auth not required
        Server-->>CLI: 200 OK / anonymous user response
        CLI-->>User: Show result
