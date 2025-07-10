# `submit`

If you need to submit a [job] to a Testflinger server through a GitHub action
rather than via the [CLI][cli], you can use the [`submit`](action.yaml) action
in a CI workflow.

## Basic Usage

### Submit from a job file

Assuming there is a previous `create-job` step in the workflow that creates a
job file and outputs the path to it, you can submit a job with the following
step:

```yaml
- name: Submit job
  id: submit-job
  uses: canonical/testflinger/.github/actions/submit@main
  with:
    poll: true
    job-path: ${{ steps.create-job.outputs.job-path }}
```

### Submit from inline job

If you wish to define your job inline, you can use the following step:

```yaml
- name: Submit job
  id: submit-job
  uses: canonical/testflinger/.github/actions/submit@main
  with:
    poll: true
    job: |
      # inline YAML for Testflinger job
```

## API

### Inputs

| Key                                | Description                                        | Required | Default                     |
| ---------------------------------- | -------------------------------------------------- | -------- | --------------------------- |
| `job`                              | Inline YAML contents of a job file.                | [^job]   |                             |
| `job-path`                         | Path to a job file.                                | [^job]   |                             |
| `poll`[^reserve_data][^poll-multi] | Track submitted job to completion.                 |          | `false`                     |
| `dry-run`                          | Don't submit job.                                  |          | `false`                     |
| `server`                           | Testflinger server address.                        |          | `testflinger.canonical.com` |
| `attachments-relative-to`          | Reference directory for relative attachment paths. |          |                             |
| `client-id`                        | Client ID for jobs requiring authentication.       | [^auth]  |                             |
| `secret-key`                       | Secret key for jobs requiring authentication.      | [^auth]  |                             |

### Outputs

- `id`: The ID of the submitted job
- `device-ip`: The IP of the reserved device (if applicable)

[^job]: One of `job` or `job-path` required.

[^reserve_data]:
    If the submitted job is a reservation job (i.e., includes `reserve_data`)
    then setting the `poll` input argument to `true` results in modified
    behaviour: the job is polled only until the reservation phase is complete,
    instead of waiting for the entire job to complete (which happens when the
    reservation timeout expires or the job is cancelled). There will be no
    output to record after the reservation so there is little point in polling
    and idly occupying the runner. However, please do remember to manually
    cancel the job after you are done with the reserved device.

[^poll-multi]: To poll a multi-device job, see the [`poll-multi`][poll-multi-action] action.

[^auth]: Both client-id and secret-key must be provided, or neither.

[job]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/reference/job-schema.html
[cli]: ../../../cli/
[poll-multi-action]: ../poll-multi/
