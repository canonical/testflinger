Authentication and Authorisation
--------------------------------

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