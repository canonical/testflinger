# Agent sub-recipes.
mod agent
# Command-line interface sub-recipes.
mod cli
# Common library sub-recipes.
mod common
# Device connectors sub-recipes.
mod device-connectors
# Server sub-recipes.
mod server
# Documentation sub-recipes.
mod docs

[doc('Describe usage and list the available recipes.')]
help:
    @echo '{{ BOLD }}Testflinger Project{{ NORMAL }}'
    @echo
    @echo 'For usage details for a specific recipe, run {{ CYAN }}just --usage RECIPE{{ NORMAL }}'
    @echo
    @just --list --unsorted

[doc('Install pre-commit hooks.')]
[group('project')]
pre-commit:
    @uvx prek install --refresh

[doc('Perform static analysis on GitHub workflows.')]
[group('lint')]
zizmor:
    @uvx zizmor --gh-token=$(gh auth token) .

[doc('Format all projects.')]
[group('lint')]
format: agent::format agent::charm::format cli::format common::format device-connectors::format server::format server::charm::format
    @echo 'All done!'

[doc('Lint all projects.')]
[group('lint')]
lint: agent::lint agent::charm::lint cli::lint common::lint device-connectors::lint server::lint server::charm::lint
    @echo 'All done!'

[doc('Run unit tests for all projects.')]
[group('test')]
test: agent::test agent::charm::test cli::test common::test device-connectors::test server::test server::charm::test
    @echo 'All done!'

[doc('Run all checks.')]
[group('test')]
check: zizmor agent::check agent::charm::check cli::check common::check device-connectors::check server::check server::charm::check
    @echo 'All done!'
