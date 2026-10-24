# Resume pruner

Open **Resume Pruner** from the sidebar or Resume Builder list. This feature handles
structured builder drafts, not uploaded PDFs. It makes no AI calls.

1. Mark one to five owned drafts as protected bases. Marking or unmarking increments
   the revision; open editors must reload before saving. Bases remain editable but
   cannot be deleted via the builder endpoint, model delete or queryset delete.
   Cloning a base produces an ordinary, unprotected draft.
2. Start a prune review. It freezes all current draft contents, titles, template
   versions, revisions and base flags. At most three reviews/backups may be active.
3. Confirm groups. Similarity uses normalized word overlap in summary, skills,
   experience, projects and education, ignoring contact and typography. Weak matches
   and close ties remain unassigned. Assign manually or leave untouched.
4. Select additions. Exact normalized duplicates are excluded. Original wording is
   preserved. Similar bullets and conflicting details are flagged for manual review.
   Contact fields and summary are optional replacements (at most one per field).
   Matching entries receive new bullets/skills; different metadata creates a separate
   entry only when approved. Different dates/roles are not automatically reconciled.
5. Select source drafts to delete; all deletion checkboxes start unchecked. Unassigned
   sources and bases cannot be selected. Rejected additions are not copied; the final
   confirmation explicitly warns that deleting a source discards that content.
6. Review full sandboxed HTML previews and the exact deletion list. These previews
   do not consume draft slots. Download the private JSON backup before confirming.
7. Confirm. Under a transaction and account/draft row locks, every reviewed snapshot
   is checked against live data. Any changed, removed or reclassified draft aborts
   the operation. The final count must be <=20. Approved sources are deleted and
   consolidated copies created atomically. Failure rolls everything back. Repeated
   confirmation does not create duplicate outputs. Bases are never modified.

New consolidated copies are not automatically bases. To promote one, unmark an old
base and mark the new copy. At most one output is created for each assigned base.
Typography and the projects heading come from the base. More than 600 suggestions
or an output exceeding renderer/editor limits requires a smaller consolidation.

## Backups and privacy

Reviews/backups are owner-only (including staff), no-store, and expire after 24 hours.
The JSON download includes each original UUID, title, structured content, revision,
template version and base flag; it remains available after confirmation until expiry.
It is a data backup, not a one-click restore/import feature. Keep it privately on your
device. Discarding a review deletes its server-side backup but never its resume drafts.
Expired records are deleted by the existing hourly PDF cleanup job and by
`python backend/manage.py cleanup_resume_pdfs`. Access is denied immediately at expiry,
even if the cleanup worker is delayed. No resume text is sent to external services.

## Deploy and verification

Run `python backend/manage.py migrate` (migration 0027), collect static files as usual,
reload the web app, and restart the Django-Q worker so hourly cleanup includes prune
reviews. There is no new queue for pruning; comparison and HTML preview are synchronous.

Tests: `python backend/manage.py test apps.product.test_resume_pruner`.
Coverage includes base protection, five-base limit, ownership/CSRF, ambiguous matching,
content merge, conflict flags, stale review and document rejection, final-count ceiling,
atomic rollback, idempotency, private backups, preview escaping and expiry cleanup.
