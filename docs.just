# Docs recipes, continue using Makefile as source of truth
set working-directory := 'docs'

[doc('Build the HTML documentation.')]
html:
    make html

[doc('Show help for the docs recipes.')]
help:
    make help

[doc('Watch, build, and serve the docs.')]
run:
    make run

[doc('Serve the built documentation.')]
serve:
    make serve

[doc('Check links in the documentation.')]
linkcheck:
    make linkcheck

[doc('Check spelling using vale.')]
spelling:
    make spelling

[doc('Check style guide compliance using vale.')]
vale:
    make vale

[doc('Check inclusive language (woke) using vale.')]
woke:
    make woke

[doc('Lint markdown files.')]
lint-md:
    make lint-md

[doc('Check accessibility using pa11y.')]
pa11y:
    make pa11y

[doc('Build PDF documentation.')]
pdf:
    make pdf

[doc('Remove files created by building the docs.')]
clean-doc:
    make clean-doc

[doc('Full clean including venv and node modules.')]
clean:
    make clean
