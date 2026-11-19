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

For frontend issues that need design review, apply `mockup-gen` before marking
the issue ready for implementation. An allowlisted user can request a new image
with `mockup-regen`. The workflow uses the issue creator's comments as feedback,
publishes a PNG to `ai/mockup-issue-<number>`, and posts the image inline at its
commit URL. A successful run replaces the request label with
`mockup-review-required`. The issue creator applies `mockup-approved` after
reviewing the latest image. Implementation requires both requirements clearance
and current mockup approval for issues that enter design review. Regeneration
invalidates the previous approval.

Triage creates the mockup labels. The OpenAI key needs image generation access,
and inline raw GitHub images require the viewer to be able to access the image
URL. For a failed generation, rerun the job or remove and reapply the request
label.
