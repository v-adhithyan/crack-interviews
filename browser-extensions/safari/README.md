# HackerLeap Safari extension

Separate Safari copy of the Chrome extension. Supports Ashby, Greenhouse and LinkedIn,
with the same saved-resume selection and authenticated Django analysis flow.
Chrome files remain unchanged. Keep extraction/security fixes in both copies.

## Local installation

In Safari versions that offer temporary extensions:
1. Safari → Settings → Advanced → Show features for web developers.
2. Developer settings → Add Temporary Extension, then select this directory.
3. Approve the unsigned-extension prompt yourself and enable the extension.
4. Open a supported job, expand its description, and click the extension toolbar icon.
5. Select your HackerLeap environment, click Connect / sign in, and grant access only
   to that host. Complete login in the connection tab and keep it open.
6. Return to the job, reopen the extension, Reload resumes, select a resume and Analyze.

Temporary installations are for development; reload/re-add after changing files.
If your Safari does not offer Add Temporary Extension, install full Xcode and run:

```sh
xcrun safari-web-extension-converter browser-extensions/safari --macos-only
```

Build/run the generated macOS app in Xcode and enable the extension in Safari.
Distribution requires Apple's packaging/signing workflow; this folder is not a signed app.

## Safari changes and privacy

- Uses Safari's promise-based `browser` namespace and removes Chrome's minimum-version key.
- Retains Manifest V3 module service worker and isolated-world script injection.
- Retains optional, restricted HackerLeap host access, session login and Django CSRF.
- Temporary job text stays in `storage.session`; no disk-storage fallback for job content.
- No extra permissions, remote scripts, cookies API or job-board API calls.
- Only the popup can request authenticated bridge operations. Requests and response
  destinations are restricted to configured HackerLeap origins.

Safari must support `storage.session`, `scripting.executeScript` and MV3 module workers.
Test with current desktop Safari; iOS and private browsing are not validated.
See ../chrome/README.md for backend setup, quotas and extraction limitations.
No additional backend changes or migrations are needed for Safari.

## Automated tests

```sh
cd browser-extensions/safari
npm ci
npx playwright install webkit
npm test
```

Tests exercise extraction fixtures in Playwright WebKit and background message/security
contracts with mocked browser APIs. WebKit tests do not load a Safari extension and do
not prove Safari permission, login, clipboard or service-worker behavior.

## Native Safari acceptance checklist (still required)

- Load without manifest/background errors and copy a job description.
- Test Ashby, Greenhouse, LinkedIn standalone and selected-job search pages.
- Grant/deny Connect; sign in; reopen popup; reload/select a resume.
- Submit in manual AI mode and verify the correct analysis page opens.
- Close the popup during submission; retry must reuse the existing analysis.
- Edit job text, close/reopen popup, verify session retention; restart Safari and verify clearing.
- Disconnect/revoke website access and verify authenticated actions stop.
- Check developer console for API/permission errors.

Native Safari testing could not be completed in this environment: Computer Use access
was unavailable and Xcode's converter was not installed. Do not treat this as release validation.
