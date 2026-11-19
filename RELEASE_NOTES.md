# Release notes

## Versioning guidelines

This project uses semantic versioning: `MAJOR.MINOR.PATCH`.

- **Major**: incompatible behavior, API, data, deployment, or migration changes that require consumers or operators to adapt.
- **Minor**: backward-compatible features, user-facing capabilities, or substantial enhancements.
- **Patch**: backward-compatible bug fixes, security fixes, documentation, tests, refactors, dependency updates, and maintenance.

The deployment workflow infers the bump from commits since the previous deployment:

- `BREAKING CHANGE:` in the commit body, or a conventional commit with `!`, means **major**.
- `feat:` or `feature:` means **minor**.
- Other commits default to **patch**.

Each generated entry includes the commit author and a concise summary. Review the generated notes before publishing when a change is ambiguous.

## Releases

Initial release: `1.0.0`.
