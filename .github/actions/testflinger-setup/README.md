# `testflinger-setup`

This action verifies connectivity to the Testflinger server and installs the required CLI tools.

## Usage

```yaml
- name: Setup Testflinger
  uses: canonical/testflinger/.github/actions/testflinger-setup@main
```

## API

### Inputs

| Key      | Description                    | Required | Default                     |
| -------- | ------------------------------ | -------- | --------------------------- |
| `server` | The Testflinger server to use. |          | `testflinger.canonical.com` |

### Outputs

This action does not produce any outputs.
