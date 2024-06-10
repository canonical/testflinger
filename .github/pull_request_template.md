## Description

<!--
Describe your changes here:

- What's the problem solved (briefly, since the issue is where this is elaborated in more detail).
- Introduce your implementation approach in a way that helps reviewing it well.
-->

## Resolved issues

<!--
- Note the Jira and GitHub issue(s) resolved by this PR (`Fixes|Resolves ...`).
- Make sure that the linked issue titles & descriptions are also up to date.
-->

## Documentation

<!--
Please make sure that...
- Documentation impacted by the changes is up to date (becomes so, remains so).
  - Public documentation is in the repository in the docs/ folder.
  - If there impacts on Canonical processes the relevant documentation should be update outside the repository, confirm that this has happened.
- Tests are included for the changed functionality in this PR. If to be merged without tests, please elaborate why.
-->

## Web service API changes

<!--
- Are there new endpoints introduced? Please detail for each of them...
  - The rationale for introducing it
  - The interface
    - the HTTP verb
    - the URL structure
    - Versioning
      - Is it expected to be long time stable? It should be versioned (e.g. `.../v2/...`)
      - ... or it expected to evolve, perhaps expected to be a system internal need or something we are expecting to iterate on still? It should be marked unstable (e.g. `.../unstable/...`)
    - the possible request body
    - the response bodies and status code(s) for success and possible failure case(s)
  - Authorization
    - What credentials are required to access the resource?
    - What automated test scenarios are included for authorization failures?
- Are there changed database queries? (... which could cause performance regressions)
- Are there required configuration changes?
- Are there DB migrations included?
- ... or other things you'd like to be aware of at deploy time?
-->

## Tests

<!--
- How was this PR tested? Please provide steps to follow so that the reviewer(s) can test on their end.
-->
