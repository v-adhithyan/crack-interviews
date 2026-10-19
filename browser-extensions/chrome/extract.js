// Runs only after the toolbar action, in the current tab's isolated world.
// Self-contained because Chrome serializes injected functions without their closures.
export function extractJob() {
  const href = new URL(location.href);
  const ashby = href.hostname === 'jobs.ashbyhq.com';
  const greenhouse = ['boards.greenhouse.io', 'job-boards.greenhouse.io', 'boards.eu.greenhouse.io', 'job-boards.eu.greenhouse.io'].includes(href.hostname);
  const linkedin = /^(?:www\.|[a-z]{2}\.)?linkedin\.com$/.test(href.hostname);
  const linkedinId = href.pathname.match(/^\/jobs\/view\/(?:[^/]*-)?(\d+)\/?$/)?.[1]
    || (/^\/jobs\/(?:search|collections)(?:\/|$)/.test(href.pathname) ? href.searchParams.get('currentJobId') : null);
  if (href.protocol !== 'https:' || (!ashby && !greenhouse && !linkedin)) {
    return {source: 'manual', title: '', company: '', description: '', url: '', warning: 'Open an Ashby, Greenhouse or LinkedIn job, or paste the job description below.'};
  }
  const isJob = linkedin ? /^\d+$/.test(linkedinId || '') : ashby ? /^\/[^/]+\/[0-9a-f-]{36}(?:\/|$)/i.test(href.pathname)
    : /\/jobs\/\d+(?:\/|$)/.test(href.pathname) || (href.pathname.startsWith('/embed/job_app') && /^\d+$/.test(href.searchParams.get('token') || ''));
  if (!isJob) return {source: 'manual', title: '', company: '', description: '', url: '', warning: 'Open an individual job posting, or paste its description below.'};
  const source = linkedin ? 'linkedin' : ashby ? 'ashby' : 'greenhouse';
  // Do not copy tracking query parameters. Preserve Greenhouse embed identifiers only.
  const canonical = new URL(linkedin ? `https://www.linkedin.com/jobs/view/${linkedinId}/` : href.origin + href.pathname);
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
    if ([].concat(value['@type'] || []).includes('JobPosting') && typeof value.description === 'string') {
      // Search pages may include metadata for a different/recommended job.
      if (linkedin) {
        const id = typeof value.url === 'string' ? value.url.match(/\/jobs\/view\/(?:[^/?]*-)?(\d+)(?:[/?]|$)/)?.[1] : null;
        if (id !== linkedinId) return null;
      }
      return value;
    }
    return findPosting(value['@graph'], depth+1);
  }
  for (const script of (linkedin && !href.pathname.startsWith('/jobs/view/') ? [] : document.querySelectorAll('script[type="application/ld+json"]'))) {
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
  let scope = document;
  if (linkedin) {
    const panes = document.querySelectorAll('.jobs-search__job-details--container, .jobs-search__job-details, .job-view-layout, .jobs-details');
    scope = Array.from(panes).find(el => el.getClientRects().length && el.querySelector('#job-details, .jobs-description__content, .jobs-description-content__text')) || document;
    if (!href.pathname.startsWith('/jobs/view/') && scope === document) {
      result.warning = 'Wait for the selected LinkedIn job details to load, then click Extract again, or paste the description.';
      return result;
    }
    const titleLink = scope.querySelector('.job-details-jobs-unified-top-card__job-title a, .jobs-unified-top-card__job-title a');
    const visibleId = titleLink?.href.match(/\/jobs\/view\/(?:[^/?]*-)?(\d+)(?:[/?]|$)/)?.[1];
    if (visibleId && visibleId !== linkedinId) {
      result.warning = 'LinkedIn is switching jobs. Wait for the selected job to load, then click Extract again.';
      return result;
    }
  }
  if (!result.description) {
    const selectors = linkedin
      ? ['#job-details', '.jobs-description-content__text', '.jobs-description__content', '.show-more-less-html__markup']
      : ashby
      ? ['.ashby-job-posting-description', '[data-testid="job-description"]', '[class*="jobDescription"]', '[class*="JobDescription"]', '[class*="descriptionText"]']
      : ['.job__description', '#content', '[data-testid="job-description"]', '.job-description'];
    for (const selector of selectors) {
      const el = linkedin ? Array.from(scope.querySelectorAll(selector)).find(node => node.getClientRects().length) : scope.querySelector(selector);
      if (el && elementText(el).length >= 40) {result.description = elementText(el); break;}
    }
  }
  if (!result.title) result.title = clean((linkedin
    ? scope.querySelector('.job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, .top-card-layout__title')
    : document.querySelector('h1'))?.textContent || '');
  if (!result.company) result.company = clean(scope.querySelector(linkedin
    ? '.job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name, .topcard__org-name-link'
    : '.company-name, .company-name-link, [data-testid="company-name"]')?.textContent || '');
  if (linkedin && result.description) result.warning = 'Detected LinkedIn job. Expand the description on LinkedIn first, then use Extract again if any text is missing. Review the selected job before submitting.';
  if (!result.description) {
    result.warning = 'Could not confidently extract this job. Paste its description below; application forms are never copied.';
    if (/^job not found$/i.test(result.title)) {
      result.title = '';
      result.warning = 'This job is no longer available. Open an active posting or paste a description.';
    }
  }
  if (result.description.length > 12000) result.warning = 'This description exceeds 12,000 characters. Shorten it before analysis; the full extracted text is available to copy.';
  // Bound untrusted page output without silently claiming a complete extraction.
  if (result.description.length > 100000) {
    result.description = result.description.slice(0, 100000);
    result.warning = 'The page text was unusually large and was truncated. Review and shorten it before using it.';
  }
  result.title = result.title.slice(0, 200); result.company = result.company.slice(0, 200);
  return result;
}
