const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {webkit} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
let browser, extractJob;
before(async () => {
  ({extractJob} = await import(pathToFileURL(path.resolve(__dirname, '../extract.js'))));
  browser = await webkit.launch({headless:true});
});
after(async () => {await browser?.close();});
async function extract(url, html) {
  const page=await browser.newPage();
  await page.route('**/*', route => route.fulfill({contentType:'text/html; charset=utf-8', body:'<meta charset="utf-8">'+html}));
  await page.goto(url);
  const result=await page.evaluate(extractJob); await page.close(); return result;
}
const ashby='https://jobs.ashbyhq.com/Example/12345678-1234-1234-1234-123456789012';
test('Ashby JSON-LD extracts description, metadata and removes tracking', async () => {
  const post={'@type':'JobPosting',title:'Backend Engineer',hiringOrganization:{name:'Example'},description:'<h2>About the role</h2><p>Build APIs.</p><ul><li>Python</li><li>Django</li></ul>'};
  const result=await extract(ashby+'?utm_source=test', `<script type="application/ld+json">${JSON.stringify({'@graph':[post]})}</script>`);
  assert.equal(result.title,'Backend Engineer'); assert.equal(result.company,'Example');
  assert.match(result.description,/• Python/); assert.equal(result.url,ashby);
});
test('Ashby DOM fallback excludes application form data', async () => {
  const result=await extract(ashby, '<h1>Engineer</h1><div class="ashby-job-posting-description"><p>Build reliable Python services for our customers.</p><form>Private application answer<input value="secret"></form></div>');
  assert.match(result.description,/Build reliable/); assert.doesNotMatch(result.description,/Private|secret/);
});
test('Greenhouse old and new layouts keep bullets without form fields', async () => {
  for(const [host,container] of [['boards.greenhouse.io','id="content"'],['job-boards.greenhouse.io','class="job__description"']]) {
    const result=await extract(`https://${host}/example/jobs/12345`, `<h1>Engineer</h1><div ${container}><p>Help build reliable software for our customers.</p><ul><li>Python experience required</li></ul><form>My private application</form></div>`);
    assert.equal(result.source,'greenhouse'); assert.match(result.description,/• Python/); assert.doesNotMatch(result.description,/private application/);
  }
});
test('Unsupported hosts and board listings require manual input', async () => {
  for(const url of ['https://jobs.ashbyhq.com.evil.test/example/jobs/123','https://jobs.ashbyhq.com/Example','https://job-boards.greenhouse.io/example']) {
    const result=await extract(url,'<h1>Job</h1><div id="content">Not a job description</div>');
    assert.equal(result.source,'manual'); assert.equal(result.description,'');
  }
});
test('Oversized text is flagged, not silently shortened to analysis limit', async () => {
  const result=await extract(ashby,`<div class="ashby-job-posting-description">${'a'.repeat(12001)}</div>`);
  assert.equal(result.description.length,12001); assert.match(result.warning,/exceeds/);
});
test('Malformed structured data falls back to description only', async () => {
  const result=await extract('https://boards.greenhouse.io/example/jobs/42', '<script type="application/ld+json">bad json</script><div id="content"><p>Build resilient systems and meaningful developer tools.</p></div><footer>Footer tracking</footer>');
  assert.match(result.description,/Build resilient/); assert.doesNotMatch(result.description,/tracking/);
});

test('Expired postings are reported without a misleading job title', async () => {
  const result=await extract(ashby,'<h1>Job not found</h1>');
  assert.equal(result.description,''); assert.equal(result.title,''); assert.match(result.warning,/no longer available/);
});

test('LinkedIn public page extracts only description and strips tracking', async () => {
  const result=await extract('https://www.linkedin.com/jobs/view/backend-engineer-1234567890/?trackingId=secret', '<h1 class="top-card-layout__title">Backend Engineer</h1><a class="topcard__org-name-link">Example</a><div class="show-more-less-html__markup"><p>Build secure services and support customers.</p><ul><li>Python experience</li></ul><form>Private application</form></div><aside>Recommended jobs</aside>');
  assert.equal(result.source,'linkedin');assert.equal(result.company,'Example');assert.equal(result.title,'Backend Engineer');
  assert.match(result.description,/• Python/);assert.doesNotMatch(result.description,/Private|Recommended/);
  assert.equal(result.url,'https://www.linkedin.com/jobs/view/1234567890/');
});
test('LinkedIn split view uses selected detail pane and ignores unrelated JSON-LD', async () => {
  const result=await extract('https://www.linkedin.com/jobs/search/?keywords=python&currentJobId=23456', '<script type="application/ld+json">{"@type":"JobPosting","url":"https://www.linkedin.com/jobs/view/999/","description":"Wrong job"}</script><h1>Search results</h1><div class="jobs-search__job-details--container"><h2 class="job-details-jobs-unified-top-card__job-title">Selected Engineer</h2><div class="job-details-jobs-unified-top-card__company-name">Selected Company</div><div id="job-details"><p>Build reliable Python services for our customers.</p></div></div>');
  assert.equal(result.title,'Selected Engineer');assert.equal(result.company,'Selected Company');
  assert.match(result.description,/Build reliable/);assert.doesNotMatch(result.description,/Wrong job/);
  assert.equal(result.url,'https://www.linkedin.com/jobs/view/23456/');
});
test('LinkedIn feed, search without a selection, and lookalike hosts require manual input', async () => {
  for(const url of ['https://www.linkedin.com/feed/','https://www.linkedin.com/jobs/search/?keywords=python','https://www.linkedin.com.evil.test/jobs/view/1234/']) {
    const result=await extract(url,'<div id="job-details">Private page text that is not a selected job.</div>');
    assert.equal(result.source,'manual');assert.equal(result.description,'');
  }
});
test('LinkedIn structured posting must match the current job ID', async () => {
  const posts=[{'@type':'JobPosting',url:'https://www.linkedin.com/jobs/view/111/',description:'Wrong role'}, {'@type':'JobPosting',url:'https://www.linkedin.com/jobs/view/222/',title:'Engineer',description:'<p>Develop software.</p>',hiringOrganization:{name:'Example'}}];
  const result=await extract('https://in.linkedin.com/jobs/view/222/', `<script type="application/ld+json">${JSON.stringify(posts)}</script>`);
  assert.equal(result.description,'Develop software.');assert.equal(result.title,'Engineer');
});
test('LinkedIn rejects a stale details pane during job navigation', async () => {
  const result=await extract('https://www.linkedin.com/jobs/search/?currentJobId=222', '<div class="jobs-search__job-details--container"><h2 class="job-details-jobs-unified-top-card__job-title"><a href="/jobs/view/111/">Old job</a></h2><div id="job-details">Old job description with enough text to be extracted.</div></div>');
  assert.equal(result.description,'');assert.match(result.warning,/switching jobs/);
});

test('LinkedIn email-linked posting supports a labelled description without legacy classes', async () => {
  const result=await extract('https://www.linkedin.com/jobs/view/4479381038/?trk=email&trackingId=example', '<main><h1>Software Engineer, Product</h1><section><h2>About the job</h2><div><p>Build reliable software products for scientists and collaborate with engineers and designers on useful tools.</p><ul><li>Python experience</li></ul></div></section><section><h2>Recommended jobs</h2>Unrelated vacancy</section></main>');
  assert.match(result.description,/Build reliable/);assert.match(result.description,/• Python/);
  assert.doesNotMatch(result.description,/Unrelated|Recommended/);assert.equal(result.title,'Software Engineer, Product');
  assert.equal(result.url,'https://www.linkedin.com/jobs/view/4479381038/');
});
test('LinkedIn labelled fallback does not copy the entire page or application forms', async () => {
  const result=await extract('https://www.linkedin.com/jobs/view/4479381038/', '<main><h2>About the job</h2><form><textarea>Private applicant text</textarea></form><aside>Unrelated vacancy</aside></main>');
  assert.equal(result.description,'');
});

const leverId = '12345678-1234-1234-1234-123456789012';
test('Lever structured descriptions support global and EU hosts', async () => {
  for (const host of ['jobs.lever.co', 'jobs.eu.lever.co']) {
    const url = `https://${host}/example/${leverId}`;
    const post = {'@type':'JobPosting', title:'Engineer', hiringOrganization:{name:'Example'}, description:'<p>Build reliable services.</p><ul><li>Python</li></ul>'};
    const result = await extract(url+'?lever-source=tracking', `<script type="application/ld+json">${JSON.stringify(post)}</script>`);
    assert.equal(result.source,'lever'); assert.equal(result.title,'Engineer'); assert.equal(result.company,'Example');
    assert.equal(result.url,url); assert.match(result.description,/• Python/);
  }
});
test('Lever fallback includes every description section and excludes application/footer content', async () => {
  const result = await extract(`https://jobs.lever.co/example/${leverId}`, `<a class="main-header-logo"><img alt="Example"></a><div class="posting-headline"><h2>Engineer</h2></div>
    <div class="section" data-qa="job-description"><p>Build reliable services for customers.</p></div>
    <div class="section"><h3>Requirements</h3><div class="posting-requirements"><ul><li>Python experience</li></ul></div></div>
    <div class="section" data-qa="salary-range">Salary: 100–120k</div>
    <div class="section" data-qa="closing-description">Flexible working hours.<form>Private answers<input value="secret"></form></div>
    <div class="last-section-apply">Apply now</div><footer>Unrelated footer</footer>`);
  assert.equal(result.title,'Engineer'); assert.equal(result.company,'Example');
  for (const text of ['Build reliable','Requirements','• Python','100–120k','Flexible working']) assert.ok(result.description.includes(text), `Missing ${text}: ${result.description}`);
  assert.doesNotMatch(result.description,/Private|secret|Apply now|Unrelated/);
});
test('Personio structured descriptions support both domains and retain only language', async () => {
  for (const suffix of ['de','com']) {
    const url = `https://example-company.jobs.personio.${suffix}/job/12345`;
    const post = {'@type':'JobPosting', title:'Engineer', hiringOrganization:{name:'Example'}, description:'<p>Build reliable services.</p>'};
    const result = await extract(url+'?language=en&utm_source=tracking#apply', `<script type="application/ld+json">${JSON.stringify(post)}</script>`);
    assert.equal(result.source,'personio'); assert.equal(result.title,'Engineer'); assert.equal(result.company,'Example');
    assert.equal(result.url,url+'?language=en'); assert.match(result.description,/Build reliable/);
  }
});
test('Personio DOM fallback keeps section titles and bullets without private form content', async () => {
  const result = await extract('https://example.jobs.personio.de/job/12345', `<h1>Engineer</h1><div class="detail-content-block-conditions">
    <div class="jb-description-item"><h2>Your tasks</h2><div class="detail-block-description">Build useful and reliable services for customers.</div></div>
    <div class="jb-description-item"><h2>Your profile</h2><ul><li>Python experience</li></ul></div>
    <form>Private application<textarea>secret</textarea></form></div><footer>Unrelated footer</footer>`);
  assert.equal(result.title,'Engineer'); assert.match(result.description,/Your tasks/); assert.match(result.description,/Your profile/);
  assert.match(result.description,/• Python/); assert.doesNotMatch(result.description,/Private|secret|Unrelated/);
});
test('Personio and Lever reject lookalikes, listings and insecure URLs', async () => {
  for (const url of [
    `https://jobs.lever.co.evil.test/example/${leverId}`, `https://eviljobs.lever.co/example/${leverId}`,
    `http://jobs.lever.co/example/${leverId}`, 'https://jobs.lever.co/example',
    'https://example.jobs.personio.de/', 'https://example.jobs.personio.de.evil.test/job/123',
    'https://example.personio.de/job/123', 'https://example.jobs.personio.com/job/not-a-job'
  ]) {
    const result = await extract(url, '<div class="detail-content-block-conditions">Private content should never be copied from this page.</div>');
    assert.equal(result.source,'manual',url); assert.equal(result.description,'',url);
  }
});
test('New providers do not extract whole-page content when description is absent', async () => {
  for (const url of [`https://jobs.lever.co/example/${leverId}`, 'https://example.jobs.personio.com/job/123']) {
    const result = await extract(url, '<main><h1>Job unavailable</h1><form>Private application data</form><aside>Other jobs</aside></main>');
    assert.equal(result.description,''); assert.match(result.warning,/Could not confidently extract/);
  }
});

test('Application links fetch only the public description without credentials or tracking', async () => {
  for (const base of ['https://smartbroker.jobs.personio.com/job/1259155', `https://jobs.lever.co/example/${leverId}`]) {
    const page = await browser.newPage();
    const requests = [];
    await page.route('**/*', route => {
      requests.push(route.request().url());
      return route.fulfill({contentType:'text/html; charset=utf-8', body:route.request().url().includes('/apply')
        ? '<form><input value="Private applicant"><textarea>Private answer</textarea></form>'
        : '<script type="application/ld+json">{"@type":"JobPosting","title":"Engineer","description":"Build reliable public services for customers."}</script>'});
    });
    await page.goto(base+'/apply?language=en&utm_source=chatgpt.com');
    await page.evaluate(() => {
      const nativeFetch = fetch;
      window.fetch = (url, options) => {window.fetchOptions = options; return nativeFetch(url, options);};
    });
    const result = await page.evaluate(extractJob);
    const canonical = base + (base.includes('personio') ? '?language=en' : '');
    assert.equal(result.url,canonical); assert.equal(result.title,'Engineer');
    assert.equal(result.description,'Build reliable public services for customers.');
    assert.doesNotMatch(result.description,/Private/); assert.ok(requests.includes(canonical));
    const options = await page.evaluate(() => window.fetchOptions);
    assert.equal(options.credentials,'omit'); assert.equal(options.redirect,'error'); assert.equal(options.referrerPolicy,'no-referrer');
    await page.close();
  }
});
test('Failed application-page fetch never falls back to applicant data', async () => {
  for (const failure of ['http','network']) {
    const page=await browser.newPage();
    await page.route('**/*', route => {
      if (route.request().url().includes('/apply')) return route.fulfill({contentType:'text/html',body:'<div class="detail-content-block-conditions">Private application data and personal answers here.</div>'});
      if (failure === 'network') return route.abort();
      return route.fulfill({status:failure === 'redirect' ? 302 : 404,headers:failure === 'redirect' ? {location:'https://example.org/'} : {},contentType:'text/html',body:'Unavailable'});
    });
    await page.goto('https://smartbroker.jobs.personio.com/job/1259155/apply?language=en');
    const result=await page.evaluate(extractJob);
    assert.equal(result.source,'personio'); assert.equal(result.description,'');
    assert.match(result.warning,/Could not load/); assert.equal(result.url,'https://smartbroker.jobs.personio.com/job/1259155?language=en');
    await page.close();
  }
});
