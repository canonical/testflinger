.. _explanation-oidc:

OpenID Connect (OIDC) Authentication
====================================

Testflinger supports OpenID Connect (OIDC) authentication for simplifying the
management of user logins. This enables integration with existing enterprise
identity systems (such as SSO providers), centralizes access control, and
allows administrators to manage user lifecycle through the identity provider
rather than the Testflinger server itself.

When OIDC is enabled, Testflinger restricts access to its resources to
authenticated users only. Users accessing the web interface or the CLI must
authenticate before they can use any functionality. When OIDC is not configured,
the server allows anonymous access.

.. seealso::

   :ref:`howto-enable-oidc`
      Steps to configure a provider and enable OIDC on a Testflinger server.

   :doc:`../../reference/oidc-config`
      Complete list of OIDC options configurable by the Testflinger Juju charm.


Provider Capabilities
---------------------

Testflinger relies on specific OIDC capabilities that the configured provider
must support:

- **Token authentication**: Testflinger uses ``client_secret_basic`` (HTTP Basic
  Auth in the Authorization header) for confidential clients, or falls back to
  including the ``client_id`` in the request body for public clients.
- **Authorization Code Flow**: required for web interface authentication, using
  the ``authorization_code`` grant type.
- **Device Authorization Flow**: required for CLI authentication, using the
  ``urn:ietf:params:oauth:grant-type:device_code`` grant type.
- **Scopes**: Testflinger requests ``openid``, ``profile``, and ``email`` scopes.
  The ``email`` claim is used as the user's stable identity within Testflinger.
- **Redirect URI**: the provider must specify a redirect URI with the following format
  for the Authorization Code Flow: ``https://<testflinger-server-hostname>/auth/callback``

Authorization Code Flow
-----------------------

This flow is used for web interface authentication. 

On initial access to the web interface, users will need to click the Sign In 
button and will be redirected to the OIDC provider's login page. After successful
authentication, the OIDC provider will redirect the user back to the Testflinger 
page and all resources will be accessible to the user.

Device Authorization Flow
-------------------------

This flow is used for CLI authentication. 

When users attempt to use the CLI, they will be prompted to visit a URL in their
browser and enter a user code. Testflinger acts as a proxy between the user and
the OIDC provider: the CLI polls the Testflinger server for the authentication
status, while the server exchanges the device code with the OIDC provider.

Once the user completes authentication, the Testflinger server issues its own
access and refresh tokens to the CLI which can be used to authenticate directly
with Testflinger without being redirected to the OIDC provider on each command
until these credentials expire.

