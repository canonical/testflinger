Generating pip-cache
####################

The pip-cache can be used for distributing this with all dependencies.
To regenerate or update the cache contents, use the following process::

  $ mkdir pip-cache
  $ cd pip-cache
  $ virtualenv -p python3 ve
  $ . ve/bin/activate
  $ pip install --download . -r requirements.txt

This will download the missing wheels or tarballs, and put them in
pip-cache for redistribution.
