# Contributing to the documentation

This document provides guidelines for contributing to the documentation of the project. It covers how to build the documentation, run checks, and ensure quality standards are met.

The documentation is hosted on Read the Docs for public access:

https://canonical-testflinger.readthedocs-hosted.com

## Syntax and style

The documentation is written in [reStructuredText (reST)][rst] which allows for rich formatting and features. For a quick reference of the commonly used syntax, such as links and cross-references, you can refer to [reST syntax guide][rst-syntax-guide] under the starter pack documentation.

## Build the documentation

The project uses _Sphinx_ to build and publish documentation. The configurations in the `docs/` folder are imported from the [`canonical/sphinx-docs-starter-pack`][starter-pack-repo] repository.

Before committing and pushing changes, it's a good practice to run documentation builds locally to verify your changes, using the provided `Makefile`. The local build commands verify that the documentation can be built successfully without technical errors. To perform quality control, see the section [Automatic checks](#automatic-checks).


### Local build

To build the documentation locally, navigate to the `docs/` directory and run the build commands:

```bash
make install
make html
```

After running `make install`, you'll have:

- A `docs/.sphinx/venv/` directory with the Python virtual environment
- All required Python packages installed
- The ability to run documentation build commands

If the HTML build is successful, you can view the built documentation by opening the `docs/_build/index.html` file in your browser. If any warnings or errors occur during the build, please address them before committing your changes.

> [!NOTE]  
> The HTML build command supports [Git LFS][git-lfs]. Files stored with git-lfs will be checked out before the documentation build. Update `docs/.gitattributes` file to change the included file types.

### Live preview

If you want to preview the documentation changes on a local server, you can use the following command:

```bash
make run
```

The documentation will be available at `http://localhost:8000`.

## Automatic checks

To ensure consistency and quality, the documentation uses automatic checks on pull requests, including build checks and a Markdown linter. These checks are run automatically on pull requests in the `docs/` directory, but you can also run them locally using the provided `Makefile`. Please make sure to address any issues raised by these checks.

More details about each check can be found in the [Starter pack documentation](https://canonical-starter-pack.readthedocs-hosted.com/latest/reference/automatic_checks/).

### Spelling check

Ensure there are no spelling errors in the documentation:

```bash
make spelling
```

The spelling check uses `Vale` for US English. The list of accepted words is centrally maintained in the `canonical/documentation-style-guide` repository.

To add exceptions for words flagged by the spelling check to this project, edit the `.custom_wordlist.txt` file.

**Note**: The `make spellcheck` command is deprecated. Use `make spelling` instead.

### Link check

Validate links within the documentation:

```bash
make linkcheck
```

If you have links in the documentation that should be ignored (for example, links to private repositories or internal resources), you can add them to the `linkcheck_ignore` variable in the `conf.py` file.

You can add redirects to make sure existing links and bookmarks continue working when you move files around. To do so, specify the old and new paths in the `redirects` setting of the `custom_conf.py` file.

### Markdown linting

Check Markdown files for formatting issues:

```bash
make lint-md
```

The Markdown linter uses [PyMarkdown][pymarkdown] to ensure that the Markdown files follow the defined style and formatting rules. The linter checks for common issues such as inconsistent heading levels, missing links, and other formatting problems.

Rules for the PyMarkdown Linter are defined in the `.sphinx/.pymarkdown.json` file.

### Inclusive language check

Check for potentially non-inclusive language:

```bash
make woke
```

The inclusive language check uses Vale with the Canonical style guide to identify potentially non-inclusive terms. By default, the check is applied to both Markdown and reStructuredText files located under the documentation directory.

The check focuses specifically on the "Canonical.400-Enforce-inclusive-terms" rule from the Canonical style guide. To add exceptions for terms flagged by the inclusive language check, edit the `.custom_wordlist.txt` file.

You can target specific files or directories:

```bash
make woke TARGET=infra/
```

### Style guide compliance check

Check for compliance with the Canonical style guide:

```bash
make vale
```

### Accessibility check

Look for accessibility issues in rendered documentation:

```bash
make pa11y
```

The `pa11y.json` file at the starter pack root provides basic defaults; to browse the available settings and options, see the [`pa11y` README][pa11y] on GitHub.

## Additional configurations

The documentation build process can be extended with custom configurations and additional Sphinx extensions. This allows you to tailor the documentation to your project's specific needs.

To add custom configurations for your project, see the *Additions to default configuration* and *Additional configuration sections* in the `conf.py` file. These can be used to extend or override the common configuration, or to define additional configuration that is not covered by the common `conf.py` file.

To add Sphinx extensions:

1. Add the extension package to the `docs/.sphinx/requirements.txt` file.
2. Include the extension in the `extensions` list in the `docs/conf.py` file.
3. Clean up the virtual environment and re-install all dependencies to ensure the new extension is recognized.

### Mermaid diagrams

To include Mermaid diagrams in your documentation, use the `mermaid` directive in your RST files. For example:

````rst
.. mermaid::

   graph TD;
       A-->B;
       A-->C;
       B-->D;
       C-->D;

````

To use Mermaid diagrams, ensure that the `sphinxcontrib.mermaid` extension is included in your `conf.py` file under `extensions`.

## Troubleshooting

### Virtual environment issues

If you encounter Python virtual environment issues, try cleaning up the environment and reinstalling all dependencies:

```bash
make clean
make install
```

## Additional resources

For more information on contributing to the documentation, refer to the following resources:

- [Starter pack documentation](https://canonical-starter-pack.readthedocs-hosted.com/latest/)
- [Sphinx documentation](https://www.sphinx-doc.org/en/master/)

[rst]: https://www.sphinx-doc.org/en/master/usage/restructuredtext/index.html
[rst-syntax-guide]: https://canonical-starter-pack.readthedocs-hosted.com/latest/reference/rst-syntax-reference/
[starter-pack-repo]: https://github.com/canonical/sphinx-docs-starter-pack
[git-lfs]: https://github.com/git-lfs/git-lfs/
[pymarkdown]: https://pymarkdown.readthedocs.io/en/latest/
[pa11y]: https://github.com/pa11y/pa11y#command-line-configuration