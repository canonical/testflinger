# `queue-status`

`queue-status` wraps `testflinger-cli queue-status <queue>` for use in CI
workflows. This may be useful as a prerequisite phase to `submit` which prunes
scheduled jobs from being submitted if their associated queue(s) are busy.

## Basic Usage

### Simple

```yaml
- name: Query queue-status of nvidia-gpu
  id: queue-status
  uses: canonical/testflinger/.github/actions/queue-status@main
  with:
    queue: nvidia-gpu
```

### As a gate for `submit`

```yaml
# e.g., in a matrix job

- name: Query queue-status of $${{ matrix.queue }}
  id: queue-status
  uses: canonical/testflinger/.github/actions/queue-status@main
  with:
    queue: $${{ matrix.queue }}

- name: Submit job
  id: submit-job
  if: ${{ fromJSON(steps.queue-status.outputs.available) > 0 }}
  uses: canonical/testflinger/.github/actions/submit@main
  with:
    poll: true
    job-path: ${{ steps.create-job.outputs.job-path }}
```

## API

Inputs (with the addition of `server`) and outputs are the same
as with `testflinger-cli queue-status <queue>`. The multi-line
string result is split by the keys of each line.

### Inputs

| Key                                | Description                                        | Required | Default                     |
| ---------------------------------- | -------------------------------------------------- | -------- | --------------------------- |
| `queue`                            | Name of Testflinger queue to query `queue-status`. | Yes      |                             |
| `server`                           | Testflinger server address.                        |          | `testflinger.canonical.com` |


### Outputs

| Key                                | Description                                        |
| ---------------------------------- | -------------------------------------------------- |
| `agents_in_queue`                  | Number of agents in the queue.                     |
| `available`                        | Number of agents with state "available".           |
| `busy`                             | Number of agents with state "busy".                |
| `offline`                          | Number of agents with state "offline".             |
| `jobs_waiting`                     | Number of jobs waiting in the queue.               |
| `jobs_running`                     | Number of jobs running on agents in the queue.     |
| `jobs_completed`                   | Number of jobs completed in the queue.             |
