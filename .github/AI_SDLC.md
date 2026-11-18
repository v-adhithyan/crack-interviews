# AI SDLC contract

The AI workflow is gated by requirements clarity. An issue labeled `ai-ready` is
triaged before any branch is created or code is changed.

If the issue is ambiguous, the workflow asks questions in an issue comment and
adds `ai-awaiting-clarification`. It must not implement the issue while that label
exists. When the issue author replies, triage runs again. Only a clear result adds
`ai-ready-to-implement`.

The implementation worker must read this file and `AGENTS.md` before changing code.

Only issues authored by, or explicitly approved by, users in `AI_ALLOWED_USERS`
are eligible. Configure it as an Actions secret or repository variable containing
comma-separated GitHub usernames. It is checked before the AI receives the issue
contents. An allowlisted user can approve an issue by adding `ai-ready` or
replying to a clarification comment.
