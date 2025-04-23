# Testflinger Device Connectors

## Generating pip-cache

The `pip-cache` can be used for distributing this with all dependencies. To
regenerate or update the cache contents, use the following process:

```shell
mkdir pip-cache
cd pip-cache
virtualenv -p python3 venv
. venv/bin/activate
pip install --download . -r requirements.txt
```

This will download the missing wheels or tarballs, putting them in a `pip-cache`
for redistribution.
