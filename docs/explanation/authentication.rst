.. _authentication:

Authentication and Authorisation
================================

Authentication requires a client_id and a secret_key. These credentials can be
obtained by contacting the server administrator with the queues you want priority
access for, the maximum priority level to set for each queue, and any restricted
queues that you need access to.

These credentials can be :doc:`set using the Testflinger CLI <../how-to/authentication>`. 

Additionally, you can also login to the server by running the following command:

.. code-block:: shell

    testflinger-cli login --client_id "my_client_id" --secret_key "my_secret_key"

Upon successful login, credentials will be cached and stored in a snap only available location. 
This allow ``testflinger-cli`` to authenticate automatically without the need to provide credentials
until the cached credentials expire. 

.. tip::
    You can also run ``testflinger-cli login`` without command line arguments if your credentials
    are located in a ``.env`` file as mentioned in :doc:`Authentication using Testflinger CLI <../how-to/authentication>`

Authorization Flows Based on Configuration and Provided Auth Parameters
=======================================================================

When the client_id and secret_key are provided:
-----------------------------------------------

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
        Server-->>CLI: 200 OK / authorized response
        CLI-->>User: Show result

When the client_id and secret_key are NOT provided:
---------------------------------------------------

When a refresh token is available:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
        Server-->>CLI: 200 OK / authenticated as token-associated user
        CLI-->>User: Show result
    
When OIDC is enabled:
^^^^^^^^^^^^^^^^^^^^^

When the refresh token is not accepted:
.......................................

.. mermaid::
    :alt: Sequence diagram showing a refresh token being rejected and the server initiating OIDC process
    :caption: Sequence diagram showing a refresh token being rejected and the server initiating OIDC process
    :align: center

    sequenceDiagram
        actor User
        participant CLI as testflinger-cli
        participant Server as testflinger-server

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
        User-->>CLI: Potential user re-issue of command?
        CLI->>Server: Retry request with new Bearer token
        Server-->>CLI: 200 OK / authenticated response
        CLI-->>User: Show result
   
When the refresh token is not available:
........................................

.. mermaid::
    :alt: Sequence diagram showing a refresh token being used and accepted
    :caption: Sequence diagram showing a refresh token being used and accepted
    :align: center

    sequenceDiagram
        actor User
        participant CLI as testflinger-cli
        participant Server as testflinger-server

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
        User-->>CLI: Potential user re-issue of command?
        CLI->>Server: Retry request with new Bearer token
        Server-->>CLI: 200 OK / authenticated response
        CLI-->>User: Show result


When OIDC is NOT enabled:
^^^^^^^^^^^^^^^^^^^^^^^^^

When the refresh token is not accepted:
.......................................

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
    
When the refresh token is not available:
........................................

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

When only one of the client_id or secret_key are provided:
..........................................................

.. mermaid::
    :alt: The CLI will reject the call as an invalid combination, nothing will be sent to the server
    :caption: The CLI will reject the call as an invalid combination, nothing will be sent to the server
    :align: center

    sequenceDiagram
        actor User
        participant CLI as testflinger-cli

        Note over User,CLI: One of client-id or secret-key
        User->>CLI: Run command with wrong number of credential args
        CLI-->>User: Show usage
