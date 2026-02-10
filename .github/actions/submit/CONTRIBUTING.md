## Auto-tagging

When you merge a pull request to `main` that involves changes to
the `submit` action, please bear in mind that a new namespaced
semantic version tag will automatically be created for the action,
e.g. `submit/v.1.3.2`.

By default, the new tag will have the patch number incremented,
unless your merge commit message includes `feat(submit):`,
indicating a minor release, or `breaking(submit):`, indicating
a major release. 

