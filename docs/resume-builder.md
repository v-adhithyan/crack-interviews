# Django resume builder

Entry point: `/app/resume-builder/`, also linked from the product sidebar. Next.js is unchanged.

## Run locally / deploy

- Install `backend/requirements.txt`. PDF export uses WeasyPrint 70.0.
- Install Pango and fonts. The backend Dockerfile includes Pango and Liberation Sans for Linux. On macOS: `brew install pango`; if necessary set `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` when starting Django.
- Run `python backend/manage.py migrate` to add `product.0017_resumedraft`.
- Restart the backend and run `collectstatic` for production.
- Use a shared Django cache and edge rate limits in multi-worker deployments. The per-account export cooldown uses Django cache `add`; the default local-memory cache is per worker. Set proxy body limits as well as application validation limits.

No existing uploaded resumes are converted or replaced by migration. Drafts start empty and have a single fixed template based on the supplied reference. Use for analysis is an explicit action that generates a PDF and replaces the account's current uploaded resume. Previous analysis text remains a snapshot in existing analysis records.

## Editing and concurrency

The browser previews after 350 ms and autosaves after 900 ms without typing. Only one save is in flight per tab; changes typed during a save are sent next. The preview sequence is invalidated at input time and older requests are aborted/ignored. Save status distinguishes unsaved changes, saving, saved, failure, and conflict. Export buttons are unavailable while changes remain unsaved.

`ResumeDraft.revision` starts at 1. A save performs a single SQL conditional update scoped to owner, draft and expected revision, atomically incrementing the revision. Zero updated rows returns HTTP 409. There is no long-running editing lock. The losing tab retains local edits, stops autosaving, and offers a recovery JSON download plus explicit reload. Network errors retain edits and permit manual retry; uncertain saves may resolve as conflicts, never silent overwrites. Recovery JSON is for manually retrieving/reapplying text, not an automatic merge or import format. A navigation warning protects unsaved edits; browser crashes can still lose them. Draft data is not persisted in browser localStorage.

PDF actions carry the saved revision. Export renders an in-memory snapshot; use-for-analysis checks the revision again inside a transaction after rendering before replacing the current resume. The existing uploaded Resume remains separate from ResumeDraft.

## Scope and safety

- Up to 20 private drafts per account, protected by product access and owner checks, including for staff.
- Fixed contact, summary, skill groups, work history and education sections; reorder/add/remove entries. One bullet per line; only `**bold**` inside experience bullets is formatted.
- No AI rewriting, automatic PDF import, raw HTML/CSS editing, public sharing, or custom template uploads.
- Django CSRF protection on mutations; private/no-store editor, preview, save and PDF responses.
- Structured validation, field/entry/body limits, escaped template text, safe JSON bootstrap, and a sandboxed iframe. The iframe uses a restrictive CSP and never executes scripts.
- PDF worker denies all URL fetches, enforces a 20-second wall timeout, limits pages/output size, and on Linux applies CPU/address-space limits. The worker only receives escaped server-rendered HTML from the fixed template. It is not a general untrusted HTML rendering service.
- Live preview scales an A4-width document to the available panel. Final PDF preview is authoritative for pagination. Font availability can affect layout; production installs Liberation Sans.

## Verification

`python backend/manage.py test apps.product.test_resume_builder`

Covers optimistic conflict handling, ownership, CSRF, validation, escaped preview, quotas, stale exports/deletes, export cooldown, renderer failure/timeout, and explicit analysis integration. Browser verification also exercises two tabs, retained conflicting text, delayed preview responses, and desktop/mobile layouts. PDF validation includes text extraction and visual inspection of one-page and multi-page samples.
