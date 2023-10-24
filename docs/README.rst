Testflinger Documentation
===========================

.. Note:: The Testflinger documentation set is built with Sphinx and reStructuredText. 
   See the `Sphinx and Read the Docs <https://canonical-documentation-with-sphinx-and-readthedocscom.readthedocs-hosted.com/>`_  guide for instructions on how to get started with Sphinx documentation.

This documentation contains `make`` targets defined in the ``Makefile`` that do various things. To get started, we will:

#. Install prerequisite software
#. View the documentation
#. Validate documentation checks

Install prerequisite software
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To install the prerequisites:

.. code-block:: shell

   make install

This will create a virtual environment (``.sphinx/venv``) and install
dependency software (``.sphinx/requirements.txt``) within it.

A complete set of pinned, known-working dependencies is included in
``.sphinx/pinned-requirements.txt``.

View the documentation
~~~~~~~~~~~~~~~~~~~~~~

To preview the documentation locally:

.. code-block:: shell

   make run

This will do several things:

* activate the virtual environment
* build the documentation
* serve the documentation on **127.0.0.1:8000**
* rebuild the documentation each time a file is saved
* send a reload page signal to the browser when the documentation is rebuilt

The ``run`` target is therefore very convenient when preparing to submit a
change to the documentation.

You can also run local checks separately before submitting the changes.

.. Important:: By default, the `fail_on_warning` attribute is enabled in the doc build configuration. Any warning messages occurred during the local build will cause failures on the server side. Please fix all warning messages before making a pull request.

Local checks
~~~~~~~~~~~~

Before committing and pushing changes, it's a good practice to run various checks locally to catch issues early in the development process.

Local build
^^^^^^^^^^^

Run a clean build of the docs to surface any build errors that would occur in RTD:

.. code-block:: shell

   make clean-doc
   make html

Spelling check
^^^^^^^^^^^^^^

Ensure there are no spelling errors in the documentation:

.. code-block:: shell

   make spelling

Inclusive language check
^^^^^^^^^^^^^^^^^^^^^^^^

Ensure the documentation uses inclusive language:

.. code-block:: shell

   make woke

Link check
^^^^^^^^^^

Validate links within the documentation:

.. code-block:: shell

   make linkcheck
