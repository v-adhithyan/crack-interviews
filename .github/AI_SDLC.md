# AI SDLC contract

The AI workflow is gated by requirements clarity. An issue labeled `ai-ready` is
triaged before any branch is created or code is changed.

If the issue is ambiguous, the workflow asks questions in an issue comment and
adds `ai-awaiting-clarification`. It must not implement the issue while that label
exists. When the issue author replies, triage runs again. Only a clear result adds
`ai-ready-to-implement`.

The implementation worker must read this file and `AGENTS.md` before changing code.

When an allowlisted user adds `ai-ready-to-implement`, the implementation worker
may create a branch and pull request. It must stop on unresolved requirements,
failing checks, or unsafe changes; it must never merge or deploy.

The implementation worker uses the OpenAI Codex GitHub Action and the same
Actions secret named `OPENAI_API_KEY` used by requirements triage.

The Codex job uses the restricted-sudo full-access profile because it must reach
GitHub's API to read the issue and create a pull request. It remains behind the
allowlist and never merges or deploys.

Only issues authored by, or explicitly approved by, users in `AI_ALLOWED_USERS`
are eligible. Configure it as an Actions secret or repository variable containing
comma-separated GitHub usernames. It is checked before the AI receives the issue
contents. An allowlisted user can approve an issue by adding `ai-ready` or
replying to a clarification comment.
