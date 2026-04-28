Secrets
=======

This document provides an overview of the overall structure and considerations
for Secrets in Testflinger.

For information on how secrets work in Testflinger, please refer to the
:doc:`Testflinger Secrets explanation <../explanation/secrets>`.

For information on how to use secrets in your jobs, please refer to the
:doc:`Use Secrets how-to guide <../how-to/use-secrets>`.

Structure
---------

Secrets in Testflinger are organized in a hierarchical structure based on 
namespaces and paths. Each secret has a *path*, which is its unique identifier within 
a client's namespace and used as *environment variable name* in the job definition, 
which is how the secret value is exposed during job execution.

Jobs that contain secrets are only valid if the secret owner has the same Testflinger 
``client-id`` as the job submitter. Once a job is successfully submitted, the secrets 
value are pre-loaded and can only be retrieved by authenticated Testflinger Agents when 
they pick up a job that specifies any secrets.

.. note::
    The ``secrets`` field is only supported in the ``test_data`` section of a job.

Paths must follow these constraints:

- Must be unique within a client's namespace
- Only alphanumeric characters, hyphens ``(-)``, underscores ``(_)`` and forward slashes ``(/)`` are allowed
- Must not start and end with a forward slash ``(/)``

Environment variable names must follow standard shell naming conventions:

- Must start with a letter or underscore
- Can only contain letters, numbers and underscores

Retention
---------

Secrets in Testflinger are by default retained for a year after which they
are automatically removed. This is to prevent stale data to pile up and to let 
users control the data retention of their private data automatically. 

Users can:

- Specify any expiration (in seconds) after which the secret is automatically removed.
- Specify no expiration. If needed, users can still remove it manually.
- Specify single use secrets. Useful if you don't want your data to be retained by 
  Testflinger and remove it immediately after its first use. 

.. note:: 

    The expiration of the secret is considered from the time it was last created or updated.

For more information on how to define expiration for a secret, 
refer to :doc:`Use Secrets how-to guide <../how-to/use-secrets>`.
