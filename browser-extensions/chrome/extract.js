// Runs only after the toolbar action, in the current tab's isolated world.
// Self-contained because Chrome serializes injected functions without their closures.
export function extractJob() {
  const href = new URL(location.href);
  const ashby = href.hostname === 'jobs.ashbyhq.com';
  const greenhouse = ['boards.greenhouse.io', 'job-boards.greenhouse.io', 'boards.eu.greenhouse.io', 'job-boards.eu.greenhouse.io'].includes(href.hostname);
  if (href.protocol !== 'https:' || (!ashby && !greenhouse)) {
    return {source: 'manual', title: '', company: '', description: '', url: '', warning: 'Open an Ashby or Greenhouse job, or paste the job description below.'};
  }
  const isJob = ashby ? /^\/[^/]+\/[0-9a-f-]{36}(?:\/|$)/i.test(href.pathname)
    : /\/jobs\/\d+(?:\/|$)/.test(href.pathname) || (href.pathname.startsWith('/embed/job_app') && /^\d+$/.test(href.searchParams.get('token') || ''));
  if (!isJob) return {source: 'manual', title: '', company: '', description: '', url: '', warning: 'Open an individual job posting, or paste its description below.'};
  const source = ashby ? 'ashby' : 'greenhouse';
  // Do not copy tracking query parameters. Preserve Greenhouse embed identifiers only.
  const canonical = new URL(href.origin + href.pathname);
  if (greenhouse && href.pathname.startsWith('/embed/')) {
    for (const key of ['for', 'token', 'gh_jid']) if (href.searchParams.has(key)) canonical.searchParams.set(key, href.searchParams.get(key));
  }
  const clean = text => text.replace(/\u00a0/g, ' ').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  function htmlText(html) {
    const template = document.createElement('template');
    template.innerHTML = String(html); // Inert template: never inserted into the page.
    return elementText(template.content);
  }
  function elementText(el) {
    const copy = el.cloneNode(true);
    copy.querySelectorAll('script,style,noscript,form,input,textarea,select,button,nav,footer,iframe,[hidden],[aria-hidden="true"]').forEach(n => n.remove());
    copy.querySelectorAll('li').forEach(n => n.prepend('• '));
    copy.querySelectorAll('br').forEach(n => n.replaceWith('\n'));
    copy.querySelectorAll('p,div,li,h1,h2,h3,h4,section,ul,ol').forEach(n => n.append('\n'));
    return clean(copy.textContent || '');
  }
  const result = {source, title: '', company: '', description: '', url: canonical.href, warning: ''};
  // Prefer structured JobPosting descriptions; ignore other structured data.
  function findPosting(value, depth=0) {
    if (!value || depth > 8) return null;
    if (Array.isArray(value)) {for (const item of value.slice(0, 100)) {const found = findPosting(item, depth+1); if (found) return found;} return null;}
    if (typeof value !== 'object') return null;
    if ([].concat(value['@type'] || []).includes('JobPosting') && typeof value.description === 'string') return value;
    return findPosting(value['@graph'], depth+1);
  }
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    if (script.textContent.length > 500000) continue;
    try {
      const post = findPosting(JSON.parse(script.textContent));
      if (post) {
        result.title = typeof post.title === 'string' ? htmlText(post.title) : '';
        result.company = typeof post.hiringOrganization?.name === 'string' ? htmlText(post.hiringOrganization.name) : '';
        result.description = htmlText(post.description);
        break;
      }
    } catch (_) { /* Try a targeted DOM extractor below. */ }
  }
  if (!result.description) {
    const selectors = ashby
      ? ['.ashby-job-posting-description', '[data-testid="job-description"]', '[class*="jobDescription"]', '[class*="JobDescription"]', '[class*="descriptionText"]']
      : ['.job__description', '#content', '[data-testid="job-description"]', '.job-description'];
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && elementText(el).length >= 40) {result.description = elementText(el); break;}
    }
  }
  if (!result.title) result.title = clean(document.querySelector('h1')?.textContent || '');
  if (!result.company) result.company = clean(document.querySelector('.company-name, .company-name-link, [data-testid="company-name"]')?.textContent || '');
  if (!result.description) result.warning = 'Could not confidently extract this job. Paste its description below; application forms are never copied.';
  if (result.description.length > 12000) result.warning = 'This description exceeds 12,000 characters. Shorten it before analysis; the full extracted text is available to copy.';
  // Bound untrusted page output without silently claiming a complete extraction.
  if (result.description.length > 100000) {
    result.description = result.description.slice(0, 100000);
    result.warning = 'The page text was unusually large and was truncated. Review and shorten it before using it.';
  }
  result.title = result.title.slice(0, 200); result.company = result.company.slice(0, 200);
  return result;
}
