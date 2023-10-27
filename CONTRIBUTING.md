# Contributing to Testflinger

## Introduction

This document provides the information needed to contribute to Testflinger,
its providers and its documentation.

## General recommendations

This is a monorepo with a subproject directory for each of the major
components of Testflinger, such as `agent`, `cli`, `device-connectors`, and
`server`.

All of the linters, format checkers, and unit tests can be run automatically.
Before pushing anything, it's a good idea to run `tox` from the root of the
subproject where you made changes.

## Signed commits required

- To get your changes accepted, please [sign your commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits). This practice is enforced by many of the CI pipelines executed in the repository (pipelines which use Canonical's [github-runner-operator](https://github.com/canonical/github-runner-operator) operated runners).
- If you have just discovered the requirement for signed commits after already creating a feature branch with unsigned commits, you can issue `git rebase --exec 'git commit --amend --no-edit -n -S' -i main` to sign them. To translate this into English:
   - `git rebase --exec`: rebases commits
   - `--exec '...'`: exec command `'...'` after each commit, creating a new commit
   - `git commit --amend --no-edit`: amend a commit without changing its message
      - `-n`: bypass pre-commit and commit-msg hooks
      - `-S`: GPG sign commit
      - `-i`: let the user see and edit the list of commits to rebase
      - `main`: to all the commits until you reach main  
- To make commit signing convenient, as per https://stackoverflow.com/a/70484849/504931, do the following:

   ```bash
   git config --global user.signingkey <your-key-id>
   git config --global commit.gpgSign true
   git config --global tag.gpgSign true
   git config --global push.gpgSign if-asked
