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

Environment variable names must follow standard shell naming conventions:

- Must start with a letter or underscore
- Can only contain letters, numbers and underscores
