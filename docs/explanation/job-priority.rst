Job Priority
============

Adding job priority to your jobs gives them the ability to be selected before
other jobs. Job priority can be specified by adding the job_priority field to
your job YAML. This field takes an integer value with a default value of 0. Jobs
with a higher job_priority value will be selected over jobs with lower value.
Using this feature requires :doc:`authenticating <./authentication>` with
Testflinger server.
