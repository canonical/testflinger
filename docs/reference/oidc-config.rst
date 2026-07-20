.. _ref-oidc-configuration:

OIDC Configuration
==================

The following configuration options control OIDC authentication for a Testflinger
server deployed via Juju charm.

.. note::

    OIDC is only enabled when all required parameters are set.
    If any is missing, the server will remain in ``BLOCKED`` status
    until the configuration is complete or the OIDC options are cleared.

.. list-table:: OIDC configuration options
   :header-rows: 1
   :widths: 30 10 60

   * - Option
     - Required
     - Description
   * - ``oidc_client_id``
     - Yes
     - The client ID issued by the OIDC provider when registering Testflinger
       as an application.
   * - ``oidc_provider_issuer``
     - Yes
     - The issuer URL of the OIDC provider. Testflinger uses this to discover
       provider metadata via ``<issuer>/.well-known/openid-configuration``.
   * - ``web_secret_key``
     - Yes
     - A secret key used by Flask to sign web session cookies. Must be a long
       random string. Generate one with:
       ``python -c 'import secrets; print(secrets.token_hex())'`` or with
       any other secure random string generator.
   * - ``oidc_client_secret``
     - No
     - The client secret issued by the OIDC provider. Required for confidential
       clients. Omit for public clients, in which case Testflinger falls back to
       sending the OIDC ``client_id`` in the request body.

For the steps to apply these options, see :ref:`howto-enable-oidc`.

For background on how OIDC authentication works in Testflinger, see
:doc:`../explanation/oidc-auth`.
