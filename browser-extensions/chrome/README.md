# HackerLeap Chrome extension

Manifest V3 extension for extracting Ashby/Greenhouse/LinkedIn job descriptions, copying them,
and analyzing a selected saved resume in HackerLeap. No build is required to run it.

## Install locally

1. Deploy/run the Django changes in this repository first (see Backend below).
2. Open `chrome://extensions` in Chrome and enable **Developer mode**.
3. Click **Load unpacked** and select this `browser-extensions/chrome` directory.
4. Pin **HackerLeap — Job to Resume Analysis** using Chrome's Extensions menu.
5. Open an individual Ashby, Greenhouse or LinkedIn job and click the extension icon.
6. Review/edit the extracted description, title, and company. **Copy job description**
   works without logging in or connecting HackerLeap.
7. Select the HackerLeap environment. For local Docker, select **localhost:8000**.
   For production, select the exact host you use after signing in (`www` or non-`www`).
8. Click **Connect / sign in** and grant access to that HackerLeap host. The extension
   creates a connection tab. If login is needed, finish signing in there.
9. Keep the connection tab open. Return to the job, reopen the extension, and click
   **Reload resumes**. Choose a saved draft or your currently selected uploaded resume.
10. Click **Analyze in HackerLeap**. The analysis/progress page opens in a new tab.

Click Chrome's extension **Reload** button after updating the extension files.
No developer account or store publication is needed for this local installation.
The extension is not published to the Chrome Web Store.

## What is supported

- `jobs.ashbyhq.com/{board}/{job-uuid}`
- `boards.greenhouse.io/{board}/jobs/{id}`
- `job-boards.greenhouse.io/{board}/jobs/{id}`
- Greenhouse's corresponding `.eu` hosts and `embed/job_app` links
- LinkedIn `/jobs/view/` postings and job search/collection pages with a selected `currentJobId`
- Manually pasted descriptions on other pages
- JSON-LD JobPosting extraction first, then targeted description containers
- Editable text and an explicit Copy button; application forms are excluded
- Saved resume titles and revisions, without transferring resume contents to Chrome
- Queued ChatGPT analysis where the account has access and quota
- Manual prompt + paste-JSON flow otherwise, including configured Claude mode
  (the app does not yet implement direct Claude analysis)

Custom employer domains/embedded frames are not automatically scraped in this version.
When detection fails or a site changes its layout, paste the description. Descriptions
are limited to 12,000 characters for analysis; oversized extraction is flagged for review.
There are no automated applications, background crawlers, or job-board API calls.

## Authentication and privacy

A dedicated `/app/extension/` tab uses your normal HackerLeap session. The extension's
service worker executes only fixed, same-origin requests in Chrome's **isolated world**
on that tab. Django enforces session access, CSRF, ownership and signed resume selections.
There are no CORS exemptions, exposed cookies, embedded secrets, bearer tokens or remote
JavaScript. Resume titles and signed selections come back to the popup; the full resume
stays on the server. A signed selection expires after 30 minutes; reload resumes to renew.

Permissions:

- `activeTab` and `scripting`: read the job only when the toolbar extension is invoked;
  execute the connection requests on the separately authorized HackerLeap tab.
- `storage`: selected environment in local storage; temporary job text/request IDs in
  session storage (memory, cleared on browser restart). No Chrome Sync storage.
- `clipboardWrite`: copy the description only on an explicit click.
- Optional HackerLeap host access: requested by Connect, not granted at installation.
  Local development host patterns cover ports, but runtime requests enforce only the
  exact configured origins/ports. No `<all_urls>`, cookies, history, or tabs permission.

Only the extension popup can invoke its service worker's connection/submission commands.
Disconnect removes the extension's host access; it does not log out the website.
The extension requires Chrome 120 or later. Incognito support has not been validated.

## Backend

From the repository root, with your backend virtual environment activated:

```sh
python backend/manage.py migrate
python backend/manage.py collectstatic --noinput
```

Reload the web app and restart the Django-Q worker. For local Docker:

```sh
docker compose up -d --build backend worker
```

Use the same Django settings/environment as your existing deployment. Migration **0023**:

- Allows a builder-only analysis without creating/replacing an uploaded `Resume`.
- Preserves an analysis snapshot if its optional uploaded resume is deleted.
- Adds a per-user idempotency key and payload digest for safe retries.

Endpoints (all session-authenticated; POST also requires CSRF):

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/app/extension/` | Signed-in connection page |
| GET | `/app/extension/resumes/` | Resume metadata, signed selections, CSRF and AI mode |
| POST | `/app/extension/analyses/` | Validate/snapshot chosen resume and queue analysis |

Submissions include `selection`, `request_id` (UUID), and `job` with `title`, `company`,
`description`, `url`, and `source`. A repeated request ID returns the existing analysis;
reusing it with different inputs returns 409. Stale/deleted resume selections return 409.
A draft submission captures its content, title, revision and template version. The selected
account resume is never changed. Analysis text is derived from validated structured content;
no synchronous PDF rendering is required. The resulting snapshot supports regeneration and
follow-up questions. Title and company are included as job-description context.

Extension submissions are capped at 20 per account per rolling 24 hours and share the
existing AI allowance. Quota consumption is serialized at the feature-flags row. No new AI
keys are needed. The worker and existing analysis-progress page are reused.

## Tests

```sh
cd browser-extensions/chrome
npm ci
npx playwright install chromium
npm test
```

Extraction fixtures cover both job boards, malformed JSON-LD, oversized content, excluded
application fields, unsupported domains, and board-listing pages. You can set
`CHROMIUM_EXECUTABLE` to use a local test browser.

Backend coverage: `python backend/manage.py test apps.product.test_extension` using your
normal test settings. Covers CSRF/auth/ownership, private metadata, draft-only snapshots,
unchanged default resumes, stale selection, duplicate requests, queue errors and quota fallback.

Before a store release, test several live job pages on both boards, install/login permissions
in regular Chrome, and the real configured AI provider in a staging account. Package only
runtime files, supply screenshots/privacy disclosures, and submit for Chrome Web Store review.

For LinkedIn, open/select the job and expand its description before extraction. The extension reads the rendered page only; it does not use LinkedIn private APIs, automate applications, or bypass sign-in. If the layout is unsupported or still loading, expand the description and click Extract again, or paste it manually. No additional host permissions are requested.
