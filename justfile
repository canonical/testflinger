mod docs  # load docs module to expose docs subcommands

set ignore-comments  # don't print comment lines in recipes

# this is the first recipe in the file, so it will run if just is called without a recipe
_short_help:
    @echo '{{BOLD}}Canonical Testflinger Monorepo{{NORMAL}}'
    @echo ''
    @echo '{{BOLD}}List all commands with {{CYAN}}just help{{NORMAL}}{{BOLD}}, or:{{NORMAL}}'
    @echo '- Run {{CYAN}}ruff{{NORMAL}} for all components: {{CYAN}}just fast-lint{{NORMAL}}'
    @echo ''
    @echo '{{BOLD}}Run individual checks for a component:{{NORMAL}}'
    @echo '- {{CYAN}}just check <component>{{NORMAL}} (Run all checks: lint, format, unit tests)'
    @echo '- {{CYAN}}just lint <component>{{NORMAL}} (Check linting issues)'
    @echo '- {{CYAN}}just format <component>{{NORMAL}} (Solves all fixable lint and formatting issues)'
    @echo '- {{CYAN}}just unit <component>{{NORMAL}} (Run unit tests)'
    @echo '- {{CYAN}}just charm-unit <component>{{NORMAL}} (runs charm unit tests for agent or server)'
    @echo '- {{CYAN}}just check-schema{{NORMAL}} (Check server schema is up to date)'
    @echo '- {{CYAN}}just schema{{NORMAL}} (Generate server schema)'
    @echo ''
    @echo '{{BOLD}}Build the docs: {{CYAN}}just docs{{NORMAL}}'

[doc('Describe usage and list the available recipes.')]
help:
    @echo 'All recipes require {{CYAN}}`uv`{{NORMAL}} to be available.'
    @just --list --unsorted --list-submodules

[doc("Run `uv add` for component, respecting repo-level version constraints, e.g. `just add agent 'pydantic>=2'`.")]
[positional-arguments]  # pass recipe args to recipe script positionally
add component +args:
    #!/usr/bin/env -S bash -eo pipefail
    shift 1  # drop $1 (component) from $@ it's just +args
    cd '{{component}}'
    uv add "${@}"

[doc("Run `uv remove` for component, e.g. `just remove agent pydantic`.")]
[positional-arguments]
remove component +args:
    #!/usr/bin/env -S bash -eo pipefail
    shift 1  # drop $1 (component) from $@
    cd '{{component}}'
    uv remove "${@}"

[doc("Run `uv lock` for component to update its lockfile.")]
lock component:
    #!/usr/bin/env -S bash -e
    cd '{{component}}'
    uv lock

# list of components with pyproject.toml (for linting)
components := 'agent cli common device-connectors server'

[doc('Run `lint` for all components, failing afterwards if any errors are found.')]
fast-lint:
    #!/usr/bin/env -S bash -eo pipefail
    FAILURES=0
    for component in {{components}}; do
        echo "=== Linting $component ==="
        cd "$component"
        uvx --with tox-uv tox run -e lint || ((FAILURES+=1))
        cd ..
    done
    : "$FAILURES command(s) failed."
    exit $FAILURES

[doc('Run all checks (format, lint, unit tests) for a component.')]
check component:
    #!/usr/bin/env -S bash -e
    cd '{{component}}'
    uvx --with tox-uv tox

[doc('Run `ruff format --check` for a component.')]
format component:
    #!/usr/bin/env -S bash -e
    cd '{{component}}'
    uvx --with tox-uv tox run -e format

[doc('Run `ruff check` for a component.')]
lint component:
    #!/usr/bin/env -S bash -e
    cd '{{component}}'
    uvx --with tox-uv tox run -e lint

[doc('Run unit tests for a component.')]
unit component:
    #!/usr/bin/env -S bash -e
    cd '{{component}}'
    uvx --with tox-uv tox run -e unit

[doc('Run charm unit tests (agent, server only).')]
charm-unit component:
    #!/usr/bin/env -S bash -e
    if [[ '{{component}}' != 'agent' && '{{component}}' != 'server' ]]; then
        echo "Error: charm-unit is only available for 'agent' and 'server'"
        exit 1
    fi
    cd '{{component}}'
    uvx --with tox-uv tox run -e charm-unit

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