const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
let browser, extractJob;
before(async () => {
  ({extractJob} = await import(pathToFileURL(path.resolve(__dirname, '../extract.js'))));
  browser = await chromium.launch({headless:true, ...(process.env.CHROMIUM_EXECUTABLE ? {executablePath:process.env.CHROMIUM_EXECUTABLE} : {})});
});
after(async () => {await browser?.close();});
async function extract(url, html) {
  const page=await browser.newPage();
  await page.route('**/*', route => route.fulfill({contentType:'text/html', body:html}));
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
