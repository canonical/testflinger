# What is Testflinger?

Testflinger is a system for orchestrating the time-sharing of access to a pool of target machines.

Each Testflinger system consists of:

- a web service (called just Testflinger) that provides an API to request jobs by placing them on a queue
- per machine agents that wait for jobs to placed on queues they can service and then process them

Jobs can be either fully automated scripts that can attempt to complete within the allocated time or interactive shell sessions.

The Testflinger system is particular useful for sharing finite machine resources between different consumers in a predictable fashion.

Typically this has been used for managing a test lab where CI/CD test runs and also exploratory testing by human operators is desired.

# Documentation

You can find more information and documentation on the [Testflinger Documentation Page](https://testflinger.readthedocs.io/en/latest/).

# Content of this repository

A full deployment of testflinger consists of the following components:

- `Testflinger Server`: The API server, and Web UI
- `Testflinger Agent`: Requests and processes jobs from associated queues on the server on behalf of a device
- `Testflinger Device Connectors`: Handles provisioning and other device-specific details for each type of device
- `Testflinger CLI`: The command-line tool for submitting jobs, checking status of jobs, and retreiving results

This monorepo is organized in a way that is consistant with the components described above:

```bash                                                                   
└── providers
    ├── server
    ├── agent
    ├── device-connectors
    ├── cli
    └── docs
```

# Github actions

If you need to submit a job to a testflinger server through a Github action (instead, for example, of using the command-line tool), you can use the [`submit` action](https://github.com/canonical/testflinger/blob/main/.github/actions/submit/action.yaml) in a CI workflow.

The corresponding step in the workflow would look like this:
```
    - name: Submit job
      uses: canonical/testflinger/.github/actions/submit@v1
      with:
        poll: true
        job-path: ${{ steps.create-job.outputs.job-path }}
```

This assumes that there is a previous `create-job` step in the workflow that creates the job file and outputs the path to it, so that it can be used as input to the `submit` action.
Alternatively, you can use the `job` argument (instead of `job-path`) to provide the contents of the job inline:
```
    - name: Submit job
      uses: canonical/testflinger/.github/actions/submit@v1
      with:
        poll: true
        job: |
            ...  # inline YAML for Testflinger job
```
In the latter case, do remember to use escapes for environment variables in the inline text, e.g. `\$DEVICE_IP`.