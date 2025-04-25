# `poll-multi`

If you need to poll a [job] submitted to a multi-device agent through a GitHub
action rather than via the [CLI][cli], you can use the
[`poll-multi`][poll-multi-action] action in a CI workflow.

## Basic Usage

Assuming you've submitted a multi-device job with the [`submit`][submit-action]
action, you can poll a job with the following step:

```yaml
- name: Poll multi-device job
  id: poll
  uses: canonical/testflinger/.github/actions/poll-multi@v1
  with:
    job-id: ${{ steps.submit.outputs.id }}
```

### Poll Until Phase

Assuming you've submitted a multi-device job with the [`submit`][submit-action]
action, you can poll a job until all child jobs reach a phase (`sentinel-phase`)
with the following step:

```yaml
- name: Poll multi-device job until reservation
  id: poll
  uses: canonical/testflinger/.github/actions/poll-multi@v1
  with:
    job-id: ${{ steps.submit.outputs.id }}
    sentinel-phase: reserve

- name: Verify job statuses
  shell: bash
  env:
    JOBS: ${{ steps.poll.outputs.jobs }}
  run: |
    echo $JOBS | jq
```

Refer to the [Outputs](#outputs) section for more information on the `jobs`
output of the action.

## API

### Inputs

| Key              | Description                                                         | Required           | Default    |
| ---------------- | ------------------------------------------------------------------- | ------------------ | ---------- |
| `job-id`         | Job ID of the parent multi-device job.                              | :white_check_mark: |            |
| `sentinel-phase` | Phase that all child jobs must reach before this action terminates. |                    | `complete` |

### Outputs

- `jobs`: A JSON string containing an array of objects with machine IPs
  (`machine-ip`) and child job IDs (`id`).

[job]: https://canonical-testflinger.readthedocs-hosted.com/en/latest/reference/job-schema.html
[cli]: ../../../cli/
[poll-multi-action]: action.yaml
[submit-action]: ../submit/
