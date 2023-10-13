Testflinger server configuration options
========================================

The configuration values of Testflinger servers are read from environment variables. If you prefer to store the configuration in a config file, the config file should be sourced prior to running the server so that the values may still be read from the environment.


.. list-table:: Testflinger server configuration options
   :header-rows: 1

   * - Field
     - Description
   * - ``MONGODB_USERNAME``
     - Username for connecting to MongoDB
   * - ``MONGODB_PASSWORD``
     - Password for connecting to MongoDB
   * - ``MONGODB_DATABASE``
     - Name of the MongoDB database to use
   * - ``MONGODB_AUTH_SOURCE``
     - Name of the database to use for authentication (Default: admin)
   * - ``MONGODB_HOST``
     - Host or IP of the MongoDB server
   * - ``MONGODB_PORT``
     - MongoDB port to connect to (Default: 27017)
   * - ``MONGODB_URI``
     - URI for connecting to MongoDB (used instead of the above config options). For example: ``mongodb://user:pass@host:27017/dbname``


Example configuration
---------------------

.. code-block:: shell

  # These values can be used in place of environment variables to configure
  # Testflinger. If MONGO_URI is not specified, then it will be built using the
  # other values specified
  MONGODB_USERNAME="testflinger"
  MONGODB_PASSWORD="testflinger"
  MONGODB_DATABASE="testflinger_db"
  MONGODB_HOST="mongo"
  MONGODB_URI="mongodb://mongo:27017/testflinger_db"