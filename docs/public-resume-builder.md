# Public resume builder launch and operations

## Included

- `/resume-builder/`: indexable landing page, example, FAQ and guide links.
- `/resume-builder/edit/`: shared Django editor, transient HTML preview, default typography,
  no autosave, leave warning, JSON recovery download/import.
- Queued anonymous PDFs: isolated private storage, session ownership, 30-minute expiry,
  duplicate snapshot reuse, same progress UI and bounded renderer as account PDFs.
- `/signup/`: public registration, Django password validators, coding access and existing
  account resume/interview features. Old invitation URLs still work; disabled existing
  accounts are not automatically reactivated.
- Explicit one-hour, session-bound transfer through login/signup. Login rotates the
  session safely; the transfer token is preserved in session data, never in a URL.
  A transfer UUID in the URL is an identifier, not an authorization credential.
  Confirmation is a CSRF-protected POST and can only create one private draft.
- Three reviewed guides using the existing CMS. Existing CMS edits are never overwritten.
- Daily aggregate funnel counters and PDF success/failure/time/byte totals. No resume
  content, account identity or raw IP is recorded in those analytics.

## Production deployment

Run in the application's virtual environment and configured Django settings:

```sh
python backend/manage.py migrate
python backend/manage.py collectstatic --noinput
python backend/manage.py publish_resume_guides
python backend/manage.py check
```

Reload the web app **and restart the Django-Q worker**. Migration 0024 creates public
jobs, handoffs, counters and the quota admission lock; 0025 widens aggregate counters.
The existing hourly PDF cleanup schedule also removes expired public jobs, handoffs
and counters. Ensure the scheduler is running. Manual cleanup:

```sh
python backend/manage.py cleanup_resume_pdfs
python backend/manage.py public_resume_metrics
```

Set `PUBLIC_RESUME_PDF_ROOT` to an absolute, writable directory shared by web and worker,
**outside any public media/static mapping**. Default: `backend/private_exports`.
Do not add a PythonAnywhere static-file mapping for this directory. Docker already
mounts a dedicated `private-exports` volume in both services. Deploy Docker with:

```sh
docker compose up -d --build backend worker
docker compose exec backend python manage.py publish_resume_guides
```

Use HTTPS and the existing secure session/CSRF configuration. `Referrer-Policy:
same-origin` preserves Django's same-origin form checks while suppressing cross-origin
referrers. Content-bearing routes include no-store and noindex headers, including errors.
Robots rules are supplementary, not access control. Only the landing page is indexed.
Set `PUBLIC_SITE_URL` to the canonical production origin.

## Limits and capacity

Admission is serialized using a database singleton lock, so it works across web workers
without relying on process-local cache. Current limits:

- Preview: 120 requests per IP/minute.
- Export: 1 pending/session, 3 new PDFs/session/hour, 10/IP/hour.
- Anonymous queue: 10 active public jobs; shared broker/registered PDF backlog threshold 50.
- Transfers: 20/IP/hour. Signup attempts: 5/IP/hour.
- Account: 20 drafts; default 2 AI analyses and 1 AI mock interview per rolling 24 hours.
  AI limits/mode remain configurable via existing feature flags; manual mode is supported.

Tune `PUBLIC_RESUME_QUEUE_LIMIT`, `PUBLIC_RESUME_GLOBAL_QUEUE_LIMIT` and
`PUBLIC_RESUME_IP_EXPORTS_PER_HOUR` to measured worker capacity. The global threshold is
an admission check, not a reservation across unrelated job producers; anonymous jobs
have their own serialized hard cap. Limit external request size at the reverse proxy
as well as the application's 100 KB limit. The renderer keeps its existing 20-second
wall timeout, Linux 768 MB/15 CPU-second bounds, 15-page and 5 MB output limits.

By default IP limits use `REMOTE_ADDR`, ignoring untrusted forwarding headers. If behind
a reverse proxy, configure `PUBLIC_RESUME_CLIENT_IP_HEADER` only to a header your proxy
**overwrites with a verified single client address**. Otherwise users behind that proxy
share its limit. Never point it at a client-controlled X-Forwarded-For value.

## Monitoring

`public_resume_metrics` reports daily `editor_start`, `pdf_requested`, `pdf_download`,
`signup`, `resume_saved`, `pdf_ready`, `pdf_failed`, `pdf_bytes`, `pdf_queue_ms` and
`pdf_render_ms` totals plus current queue states. Starts count first preview per session
per day; downloads count the first attachment response per job, not confirmed receipt.
Aggregate metrics expire after 90 days. Rate-limit identifiers are separate short-lived
keyed hashes; daily IP-key rotation prevents indefinite linkage.

Renderer logs contain duration, queue latency, output bytes, peak memory, CPU milliseconds
and page count. They do not log resume text. Watch failure ratio, queue time and worker
resource usage before raising limits. No third-party analytics script is introduced.

## Verification

Backend coverage includes CSRF, invalid input, default-font enforcement, no preview draft
storage, session isolation, expiry/cleanup, worker failure, duplicate exports, session/IP/
queue caps, forwarding-header spoofing, signup transfer ownership/idempotency, and CMS
publication without overwrites. Existing product/website tests also run.

Browser smoke flow: anonymous editing → real queued PDF → separate-session denial →
signup → private draft → original editor survives CSRF rotation. Check at desktop and
390px mobile widths, including keyboard focus, form labels, live status and tab controls.
Use synthetic content. Full accessibility audit and production load testing are separate
from these functional checks; the conservative limits are not a measured capacity claim.

## Data lifecycle

Preview text is rendered but not persisted as a draft. PDF snapshots clear on success or
failure; expired snapshots/files are removed on cleanup. Handoff content clears on claim
or expires in one hour. Expiry blocks reads immediately; physical cleanup may lag until
the next hourly run. JSON recovery files remain on the visitor's device until they delete
them. Closing an unsaved editor without a recovery copy loses its in-memory content.
