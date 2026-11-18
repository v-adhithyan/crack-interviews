# AI development rules

- Read the complete issue and all clarification replies before editing code.
- Do not implement an issue with the `ai-awaiting-clarification` label.
- Make the smallest complete change and preserve existing behavior outside the issue.
- Add or update meaningful unit, integration, and regression tests.
- Run `python manage.py check` and `python manage.py makemigrations --check --dry-run` for backend changes.
- Run the relevant Django tests; run frontend lint/build for frontend changes.
- Do not modify secrets, production data, or deployment credentials.
- Open a pull request for review. Never merge or deploy your own changes.

## Issue allowlist

The issue triage workflow only processes issues authored by, or explicitly
approved by, a user listed in the repository variable `AI_ALLOWED_USERS`. Set it
to comma-separated GitHub logins, for example `alice,bob`. An allowlisted user can
approve an issue by adding the `ai-ready` label or replying to a clarification.
Keep it empty until the allowlist is configured.
