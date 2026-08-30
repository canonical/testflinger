# Preface

This directory holds the Sphinx documentation site for Testflinger, hosted on Read the Docs.
Read the top-level `.kb/agents.md` file before continuing below.


# Important

- Build documentation with `just html`.
- Run the narrowest applicable validation recipe: `just linkcheck`, `just lint-md`, `just spelling`, `just woke`, `just vale`, or `just pa11y`.


# Directory

- `tutorial/` - Getting-started guides.
- `how-to/` - Task-oriented guides.
- `reference/` - API, schema, and job reference documentation.
- `explanation/` - Conceptual background.
- `reuse/` - Reusable documentation fragments and examples.
- `images/` - Documentation images.
- `conf.py` - Sphinx configuration.
- `index.rst` - Documentation site root/index.
- `justfile` / `Makefile` / `make.bat` - Build entry points.
