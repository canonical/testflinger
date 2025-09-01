Reserve a device
================

When you only need an SSH access to the DUT to manually interact with it, you can use a reserve job.

To reserve a device, provide a job definition as the following:

.. code-block:: yaml

  job_queue: <queue>
  provision_data:
    <providion-data>
  reserve_data:
    ssh_keys:
      - <id-provider>:<your-username>
    timeout: <maximum-reservation-duration-seconds>

In the ``reserve_data``, you will find:

- ``ssh_keys``: Specifies the list of public SSH keys to use for reserving the device. Each line includes an identity provider name and your username on the provider's system. Supported identities are LaunchPad (``lp``) and GitHub (``gh``).
- ``timeout``: Specifies the reservation time in seconds, default is 1 hour (3600), maximum is 6 hours (21600) without authentication.

If you need more time, see information on authentication and authorisation at :doc:`../how-to/authentication`.

Then submit the job with:

.. code-block:: shell

  $ testflinger-cli submit --poll reserve-job.yaml

Once the device is ready, Testflinger will print out an SSH command that you can use to to access to the device.

When you are finished with the device, you can end your reservation early by cancelling the job. See :doc:`../how-to/cancel-job`.
