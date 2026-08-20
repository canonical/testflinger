# Preface

Testflinger Server is the Flask REST API and web UI that manages the job queue: accepting submissions, persisting job state, and handing out jobs to agents.
Read the top-level `.kb/agents.md` file before continuing below.


# Important

- When changing the public API, regenerate `schemas/openapi.json` with `just schema`; `just check` verifies that the schema is current.


# Directory

- `src/testflinger/` - Server source: `application.py` (Flask app), `api/` and `views.py` (routes), `database.py` (MongoDB), `oidc/` (SSO), `secrets/`, `owasp/` (security utilities).
- `tests/` - Unit tests.
- `schemas/` - OpenAPI specification.
- `charm/` - Kubernetes charm for production deployment.
- `terraform/` - Infrastructure-as-code for deployment.
- `devel/` - Local development helpers (sample data, SSO test config).
- `scripts/` - Utility scripts.
- `docker-compose.yml` - Local containerized dev environment.
- `Dockerfile` - Builds the OCI image consumed by the `charm/` for production deployment.
- `app.py` - WSGI entry point.
- `justfile` - Task runner (`just serve`, `just populate`, `just admin`, format/lint/test/check).
