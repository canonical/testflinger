Search Jobs
=============

You can search for jobs based on the following criteria:
   * tags
   * state


Searching by Tags
------------------

Tags can make it easier to find related jobs later. For instance, tools like
spread have a need to find currently running jobs so that they can be
cancelled once they are done using those devices for their testing.

To add tags to a job submission, add a section like this with one or more tags
in your job yaml:

.. code-block:: yaml

      tags:
        - myproject
        - client

Testflinger doesn't use any of this information, but it makes it easier for
you to search for those jobs later.

The search API allows you to search for jobs based on tags and state. To
search for a jobs by tag, you can provide one or more tags in the query string:

.. code-block:: console

      $ curl 'http://localhost:8000/v1/job/search?tags=foo&tags=bar'

By default, the search API will return jobs that match any of the tags. To
require that all tags match, you can provide the "match" query parameter with
the value "all":

.. code-block:: console

      $ curl 'http://localhost:8000/v1/job/search?tags=foo&tags=bar&match=all'

Searching by Job State
-----------------------

By default, the search API will only return jobs that are not already marked as
cancelled or completed. To specify searching for jobs in a specific state, you
can provide the "state" query parameter with one of the
:doc:`test phases <../reference/test-phases>`:

.. code-block:: console

      $ curl 'http://localhost:8000/v1/job/search?state=provision'

You can also search specify more than one state to match against. Obviously,
since a job can only be in one state at a given moment, the matching mode
for this will always be "any".

.. code-block:: console

      $ curl 'http://localhost:8000/v1/job/search?state=cancelled&state=completed'

This can be done with or without providing tags in the search query.
