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

## 1.0.1 - 2026-11-19

Release type: **patch**.

- fix release notes bump — v-adhithyan (aavispeaks@gmail.com), `cb759c0`

## 1.0.2 - 2026-11-19

Release type: **patch**.

- Merge pull request #1 from v-adhithyan/growth-hacking/public-resume-builder — Adhithyan Vijayakumar (aavispeaks@gmail.com), `1ff81fc`

- Keep public navigation labels on one line — Codex (codex@openai.com), `d8e0a52`

- Resolve main conflicts and align public resume PDF actions — github-actions[bot] (41898282+github-actions[bot]@users.noreply.github.com), `9b5662a`

- add public growth hacking page — v-adhithyan (aavispeaks@gmail.com), `b790709`

- remove extension usage allowance — v-adhithyan (aavispeaks@gmail.com), `a976f79`

- public resume builder - initial commit — v-adhithyan (aavispeaks@gmail.com), `a825787`

## 1.0.3 - 2026-11-19

Release type: **patch**.

- Merge pull request #22 from v-adhithyan/ai/issue-21 — Adhithyan Vijayakumar (aavispeaks@gmail.com), `f768483`

- Limit public signups to ten per IST day — github-actions[bot] (41898282+github-actions[bot]@users.noreply.github.com), `f534c19`

## 1.0.4 - 2026-11-19

Release type: **patch**.

- Merge pull request #25 from v-adhithyan/ai/issue-24 — Adhithyan Vijayakumar (aavispeaks@gmail.com), `67baf31`

- Add five approved resume builder comparisons — github-actions[bot] (41898282+github-actions[bot]@users.noreply.github.com), `93c6903`
