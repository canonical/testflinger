mod docs  # load docs module to expose docs subcommands

set ignore-comments  # don't print comment lines in recipes

# this is the first recipe in the file, so it will run if just is called without a recipe
_short_help:
    @echo '{{BOLD}}Canonical Testflinger Monorepo{{NORMAL}}'
    @echo ''
    @echo '{{BOLD}}List available components in this monorepo with {{CYAN}}just list-components{{NORMAL}}'
    @echo ''
    @echo '{{BOLD}}List all commands with {{CYAN}}just help{{NORMAL}}{{BOLD}}, or:{{NORMAL}}'
    @echo '- Run all checks for all components: {{CYAN}}just check-all{{NORMAL}}'
    @echo '- Run {{CYAN}}ruff format{{NORMAL}} for all components: {{CYAN}}just format-all{{NORMAL}}'
    @echo '- Run {{CYAN}}ruff{{NORMAL}} for all components: {{CYAN}}just lint-all{{NORMAL}}'
    @echo '- Run unit tests for all components: {{CYAN}}just unit-all{{NORMAL}}'
    @echo ''
    @echo '{{BOLD}}Run individual checks for a component:{{NORMAL}}'
    @echo '- {{CYAN}}just check <component>{{NORMAL}} (Run all checks: lint, format, unit tests)'
    @echo '- {{CYAN}}just lint <component>{{NORMAL}} (Check linting issues)'
    @echo '- {{CYAN}}just format <component>{{NORMAL}} (Solves all fixable lint and formatting issues)'
    @echo '- {{CYAN}}just unit <component>{{NORMAL}} (Run unit tests)'
    @echo '- {{CYAN}}just check-schema{{NORMAL}} (Check server schema is up to date)'
    @echo '- {{CYAN}}just schema{{NORMAL}} (Generate server schema)'
    @echo ''
    @echo '{{BOLD}}Show help for the docs recipes: {{CYAN}}just docs help{{NORMAL}}'
    @echo '{{BOLD}}Build the docs: {{CYAN}}just docs{{NORMAL}}'

# === COMPONENT DEFINITIONS ===

# Testflinger main components
tf_components := 'agent cli common device-connectors server'

# Testflinger Charm components
charm_components := 'agent-charm server-charm'

# All components
all_components := tf_components + ' ' + charm_components

# Resolves a component name to its directory path
_path component:
    @case '{{component}}' in \
        agent-charm) echo 'agent/charms/testflinger-agent-host-charm' ;; \
        server-charm) echo 'server/charm' ;; \
        *) echo '{{component}}' ;; \
    esac

# === RECIPE DEFINITIONS ===

[doc('Describe usage and list the available recipes.')]
help:
    @echo 'All recipes require {{CYAN}}`uv`{{NORMAL}} to be available.'
    @just --list --unsorted --list-submodules

[doc('List available components in monorepo.')]
list-components:
    @echo '{{all_components}}'

# --- All-components recipes ---

[doc('Run all checks (format, lint, unit tests) for all components.')]
check-all:
    #!/usr/bin/env -S bash -e
    FAILURES=0
    for component in {{all_components}}; do
        echo "=== Checking $component ==="
        just check "$component" || ((FAILURES+=1))
    done
    echo "$FAILURES component(s) failed."
    exit $FAILURES

[doc('Run `ruff format` for all components, failing afterwards if any errors are found.')]
format-all:
    #!/usr/bin/env -S bash -e
    FAILURES=0
    for component in {{all_components}}; do
        echo "=== Formatting $component ==="
        just format "$component" || ((FAILURES+=1))
    done
    echo "$FAILURES component(s) failed."
    exit $FAILURES

[doc('Run `lint` for all components, failing afterwards if any errors are found.')]
lint-all:
    #!/usr/bin/env -S bash -e
    FAILURES=0
    for component in {{all_components}}; do
        echo "=== Linting $component ==="
        just lint "$component" || ((FAILURES+=1))
    done
    echo "$FAILURES component(s) failed."
    exit $FAILURES

[doc('Run `unit` for all components, failing afterwards if any errors are found.')]
unit-all:
    #!/usr/bin/env -S bash -e
    FAILURES=0
    for component in {{all_components}}; do
        echo "=== Running unit tests for $component ==="
        just unit "$component" || ((FAILURES+=1))
    done
    echo "$FAILURES component(s) failed."
    exit $FAILURES

# --- Per-component recipes ---

[doc('Run all checks (format, lint, unit tests) for a component.')]
check component:
    #!/usr/bin/env -S bash -e
    cd "$(just _path '{{component}}')"
    uvx --with tox-uv tox

[doc('Run `ruff format --check` for a component.')]
format component:
    #!/usr/bin/env -S bash -e
    cd "$(just _path '{{component}}')"
    uvx --with tox-uv tox run -e format

[doc('Run `ruff check` for a component.')]
lint component:
    #!/usr/bin/env -S bash -e
    cd "$(just _path '{{component}}')"
    uvx --with tox-uv tox run -e lint

[doc('Run unit tests for a component.')]
unit component:
    #!/usr/bin/env -S bash -e
    cd "$(just _path '{{component}}')"
    uvx --with tox-uv tox run -e unit

# --- Server schema recipes ---

[doc('Validate server schema is up to date.')]
check-schema:
    #!/usr/bin/env -S bash -e
    cd 'server'
    uvx --with tox-uv tox run -e check-schema

[doc('Generate server schema.')]
schema:
    #!/usr/bin/env -S bash -e
    cd 'server'
    uvx --with tox-uv tox run -e schema

# --- Server development recipes ---

[doc('Build and start the local server docker compose stack.')]
server-up:
    #!/usr/bin/env -S bash -e
    cd 'server'
    docker compose up -d --build

[doc('Rebuild and restart only the local testflinger server container.')]
server-restart:
    #!/usr/bin/env -S bash -e
    cd 'server'
    docker compose up -d --build --no-deps testflinger

[doc('Stop and remove the local server docker compose stack.')]
server-down:
    #!/usr/bin/env -S bash -e
    cd 'server'
    docker compose down --remove-orphans

[doc('Follow the local server container logs, reconnecting on restart.')]
server-logs:
    #!/usr/bin/env -S bash -e
    while true; do
        docker logs -f testflinger-server || true
        sleep 1
    done

[doc('Create a large pre-canned sample data set on the local server.')]
add-sample-data:
    #!/usr/bin/env -S bash -e
    server/devel/create_sample_data.py \
        -s http://localhost:5000 \
        -a 3000 \
        -j 500 \
        -q 4300 \
        -d 2

# --- Package management recipes ---

[doc("Run `uv add` for component, respecting repo-level version constraints, e.g. `just add agent 'pydantic>=2'`.")]
[positional-arguments]  # pass recipe args to recipe script positionally
add component +args:
    #!/usr/bin/env -S bash -e
    shift 1  # drop $1 (component) from $@ it's just +args
    cd "$(just _path '{{component}}')"
    uv add "${@}"

[doc("Run `uv remove` for component, e.g. `just remove agent pydantic`.")]
[positional-arguments]
remove component +args:
    #!/usr/bin/env -S bash -e
    shift 1  # drop $1 (component) from $@
    cd "$(just _path '{{component}}')"
    uv remove "${@}"

[doc("Run `uv lock` for component to update its lockfile.")]
lock component:
    #!/usr/bin/env -S bash -e
    cd "$(just _path '{{component}}')"
    uv lock
