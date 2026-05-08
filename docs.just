# Docs recipes, continue using Makefile as source of truth
set working-directory := 'docs'

[doc('Watch, build, and serve the docs.')]
run:
    make run

[doc('Show help for the docs recipes.')]
help:
    @just --list docs --unsorted

[doc('Only remake demo tapes with vh.')]
vhs:
    make vhs

[doc('Build the HTML documentation.')]
html:
    make html

[doc('Serve the built documentation.')]
serve:
    make serve

[doc('Remove files created by building the docs.')]
clean-doc:
    make clean-doc

[doc('Full clean including venv and node modules.')]
clean:
    make clean

[doc('Check out Git LFS files used by the documentation.')]
check-lfs:
    make check-lfs

[doc('Check links in the documentation.')]
linkcheck:
    make linkcheck

[doc('Lint markdown files.')]
lint-md:
    make lint-md

[doc('Check spelling using vale.')]
spelling:
    make spelling

[doc('Check inclusive language (woke) using vale.')]
woke:
    make woke

[doc('Check accessibility using pa11y.')]
pa11y:
    make pa11y

[doc('Check style guide compliance using vale.')]
vale:
    make vale

[doc('Build PDF documentation.')]
pdf:
    make pdf
