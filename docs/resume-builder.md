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

## Apply analysis suggestions

Select a saved builder resume with **Use for analysis**, then run a new analysis.
The analysis now receives exact summary/bullet targets and may return `resume_edits`
with `target_id`, `original`, `replacement`, and `reason`. Both manual prompts and
ChatGPT API requests use this contract (the existing Claude adapter remains unimplemented).
Older analysis JSON remains readable.

On the analysis result, **Regenerate resume** opens a review page. Select accurate
suggestions and click **Create improved resume**. This creates a separate draft in
the same template, ready for editing and PDF download. No AI request is made when
applying edits. The currently selected analysis resume is not replaced automatically.

`Resume.builder_snapshot` records the selected draft UUID, revision, template version,
title and content; each `ResumeAnalysis` stores its own copy. Uploading an external PDF
clears the current resume's builder association. Existing selections must be selected
again to capture provenance. External PDFs require a separate import workflow and
cannot be regenerated directly. Later source-draft changes are not merged into the
analyzed snapshot; the review page explains this explicitly.

GET `/app/analysis/<uuid>/resume-edits/` reviews suggestions. POST to its `apply/`
subpath accepts `plan_token` plus selected `targets`. Both require ownership, even
for staff. The POST requires CSRF, verifies a hash of the snapshot/result, validates
exact originals and allowed targets, rejects duplicate or invalid edits, and validates
the final content. Text is escaped through the existing renderer. Suggestions do not
provide a guarantee of factual accuracy: the user reviews the wording before applying.

Application locks the user and analysis briefly in a transaction, enforces the 20-draft
limit, and records `ResumeEditApplication`. Its unique analysis/application key makes
identical submissions idempotent. A deleted output produces a conflict rather than
silently recreating it. No database lock is held during AI calls or PDF rendering.
Manual JSON submissions identify the analysis UUID so an older tab cannot attach a
result to a newer analysis. Existing draft revision checks continue to protect editing.

Migration: `0018_resume_builder_snapshot_and_more`. Rebuild both backend and worker
when using Docker Compose; the backend startup applies migrations.

Recommended keywords can also be selected on the review page and added to an existing
Skills group or a new “Additional skills” group. All selections start unchecked and
require confirmation of actual experience. Case/Unicode-normalized duplicates and
keywords already present as comma/semicolon/newline/bullet/pipe-separated skills are
excluded. This is exact normalized matching, not semantic synonym detection.
Keyword-only regeneration is supported. Selected keyword IDs are resolved from the
stored analysis, included in the application key/audit, and checked against the same
stale-result token and resume size limits as wording edits.

## PythonAnywhere / uWSGI PDF subprocess

Under uWSGI, `sys.executable` can point to `/usr/local/bin/uwsgi` rather than Python.
The PDF renderer uses `sys.prefix/bin/python` to retain the active virtualenv and
its WeasyPrint dependencies. It does not resolve the virtualenv executable symlink.
If the hosting environment does not set `sys.prefix` to the app virtualenv, configure:

```sh
RESUME_PDF_PYTHON=/home/hackerleap/.virtualenvs/hackerleap.pythonanywhere.com/bin/python
```

Set this in the web app's environment (or in WSGI configuration before Django loads),
then reload the web app. The value must be an absolute executable path. This fixes
`unable to load configuration from .../resume_pdf_worker.py` when the attempted
command starts with `uwsgi`. Worker exceptions and stderr remain logged.

## Queued PDF preview and download

Preview PDF and Download PDF POST to the existing export URL with the saved revision.
They now redirect immediately to a private progress page. A `ResumePdfJob` stores the
immutable content snapshot; the Django-Q worker renders it and stores the PDF privately.
The live HTML preview stays synchronous and lightweight. **Use for analysis still
renders synchronously**; this change only moves the two PDF export actions to the queue.

Status and file endpoints under `/app/resume-pdf/<uuid>/` require the owning account,
including for staff. Downloads use FileResponse and never expose a storage URL.
Artifacts are reusable for preview/download of the same revision for one hour. Polling
reports queued/processing/ready/failed/expired states; failures offer a new export.
A queue wait over five minutes or processing over two minutes is marked failed, so a
lost worker does not leave the UI spinning forever. Duplicate task deliveries cannot
claim an already-running job. New export requests use a per-user database lock, allow
one pending export per user, and cap new exports at ten per ten minutes.

Migrations 0020/0021 create jobs and install an hourly Django-Q cleanup schedule.
Expired PDFs are immediately inaccessible and are deleted on the next cleanup run;
deleting a draft/account also removes its job files. `python manage.py cleanup_resume_pdfs`
can run cleanup manually. The worker and web process must share the private MEDIA_ROOT
(or a common private storage backend). Keep `/media/private/` inaccessible to direct
public HTTP requests, as with existing resumes. Snapshot content is cleared on success
or failure. File names are random job UUIDs, and job rows are removed after expiry.

Deploy both web and Django-Q code, run migrations and collectstatic, reload the web app,
and restart the PythonAnywhere always-on qcluster task. Without a running worker, jobs
remain queued until the five-minute timeout. The existing queue is shared with analysis;
worker concurrency and hosting memory must be sized for the bounded PDF subprocesses.
