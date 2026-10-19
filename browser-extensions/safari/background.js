import {allowedOrigin, BRIDGE, permissionPattern} from './config.js';

// Runs in the ISOLATED world of our own connection tab, never on a job board.
async function bridgeRequest(origin, operation, body) {
  if (location.origin !== origin || location.pathname !== '/app/extension/') {
    return {error: 'Open the HackerLeap connection tab and finish signing in, then reload resumes.'};
  }
  async function request(path, options={}) {
    const response = await fetch(path, {credentials: 'same-origin', redirect: 'error', cache: 'no-store', signal: AbortSignal.timeout(25000), ...options});
    const data = await response.json().catch(() => ({detail: 'HackerLeap did not return JSON. Deploy the extension backend and sign in.'}));
    if (!response.ok) throw new Error(data.detail || 'HackerLeap request failed.');
    return data;
  }
  try {
    const account = await request('/app/extension/resumes/');
    if (operation === 'resumes') {
      const {csrf_token, ...safe} = account;
      return {data: safe};
    }
    if (operation !== 'submit') return {error: 'Unsupported action.'};
    return {data: await request('/app/extension/analyses/', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': account.csrf_token}, body: JSON.stringify(body)
    })};
  } catch (error) {return {error: error.message};}
}

async function connection(origin, create=false) {
  allowedOrigin(origin);
  if (!await browser.permissions.contains({origins: [permissionPattern(origin)]})) throw new Error('Click Connect to allow access to HackerLeap.');
  const tabs = await browser.tabs.query({url: origin + '/*'});
  let tab = tabs.find(t => t.url === origin + BRIDGE);
  if (!tab && create) tab = await browser.tabs.create({url: origin + BRIDGE, active: false});
  if (!tab) throw new Error('Keep the HackerLeap connection tab open, then click Connect.');
  // Navigation is checked again inside the injected function to prevent a tab-navigation race.
  for (let i=0; i<40; i++) {
    const current = await browser.tabs.get(tab.id);
    if (current.status === 'complete') return current;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw new Error('HackerLeap is still loading. Finish signing in, then reload resumes.');
}

async function handle(message) {
  const origin = allowedOrigin(message.origin);
  if (!['connect', 'resumes', 'submit'].includes(message.type)) throw new Error('Unsupported action.');
  const tab = await connection(origin, message.type === 'connect');
  const results = await browser.scripting.executeScript({target: {tabId: tab.id}, world: 'ISOLATED',
    func: bridgeRequest, args: [origin, message.type === 'submit' ? 'submit' : 'resumes', message.body || null]});
  const result = results[0]?.result;
  if (!result || result.error) {
    if (message.type === 'connect') await browser.tabs.update(tab.id, {url: origin + BRIDGE, active: true});
    throw new Error(result?.error || 'Connection interrupted. Try reconnecting.');
  }
  if (message.type === 'submit') {
    const url = new URL(result.data.url, origin);
    if (url.origin !== origin || !/^\/app\/analysis\/[0-9a-f-]{36}\/$/.test(url.pathname) || url.search || url.hash) throw new Error('Unexpected analysis destination.');
    // The service worker completes this even if the popup closes during the request.
    await browser.storage.session.set({lastAnalysis: {url: url.href, status: result.data.status}});
    await browser.tabs.create({url: url.href});
  }
  return result.data;
}

browser.runtime.onMessage.addListener((message, sender, respond) => {
  // No content-script, external-webpage, or arbitrary extension-page callers.
  if (sender.id !== browser.runtime.id || sender.url !== browser.runtime.getURL('popup.html')) return false;
  handle(message).then(data => respond({data})).catch(error => respond({error: error.message}));
  return true;
});
