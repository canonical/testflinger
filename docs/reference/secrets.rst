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

Secrets in Testflinger are organized in a hierarchical structure based on paths.
Each secret has a *path*, its unique identifier within your client namespace;
and an *environment variable name*, which is how the secret value is exposed
during job execution. These are defined independently in the job definition.

.. note::
    The ``secrets`` field is only supported in the ``test_data`` section of a job.

The following constraints apply when defining secrets:

Paths:

- Must be unique within your client namespace
- Only alphanumeric characters, hyphens ``(-)``, underscores ``(_)`` and forward slashes ``(/)`` are allowed

Environment variable names:

- Must start with a letter or underscore
- Can only contain letters, numbers and underscores
