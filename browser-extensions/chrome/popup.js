import {DEFAULT_ORIGIN, allowedOrigin, permissionPattern} from './config.js';
import {extractJob} from './extract.js';
const $ = id => document.getElementById(id);
let tab, stateKey, job = {title: '', company: '', description: '', source: 'manual', url: ''};
let choices = [], requestId = crypto.randomUUID(), selectedId = '', busy = false;
let persistChain = Promise.resolve();
const origin = () => allowedOrigin($('origin').value);
function status(text, error=false) {$('status').textContent = text; $('status').classList.toggle('error', error);}
function syncJob() {
  job.title = $('job-title').value; job.company = $('company').value; job.description = $('description').value;
}
function update() {
  const length = $('description').value.length;
  $('length').textContent = `${length.toLocaleString()} / 12,000 characters for analysis`;
  $('length').classList.toggle('error', length > 12000);
  $('copy').disabled = !length || busy;
  $('analyze').disabled = busy || !length || !job.description.trim() || length > 12000 || !$('resume').value;
}
function persist() {
  if (!stateKey) return Promise.resolve();
  const value = {job: {...job}, requestId, selectedId, tabUrl: tab?.url, origin: origin()};
  persistChain = persistChain.catch(() => {}).then(() => chrome.storage.session.set({[stateKey]: value}));
  return persistChain;
}
function displayJob() {
  $('job-title').value = job.title; $('company').value = job.company; $('description').value = job.description;
  $('source').textContent = job.warning || (job.source === 'manual' ? 'Manually pasted job description' : `Detected ${({ashby: 'Ashby', linkedin: 'LinkedIn', greenhouse: 'Greenhouse', personio: 'Personio', lever: 'Lever'}[job.source] || job.source)} job. Review the description before submitting.`);
  update();
}
async function rpc(type, body) {
  const result = await chrome.runtime.sendMessage({type, origin: origin(), body});
  if (!result || result.error) throw new Error(result?.error || 'The extension connection was interrupted.');
  return result.data;
}
async function extract() {
  if (!tab?.id) throw new Error('Open a job page first.');
  const results = await chrome.scripting.executeScript({target: {tabId: tab.id}, world: 'ISOLATED', func: extractJob});
  job = results[0].result;
  if (!job) throw new Error('Unable to extract this page. Paste the description instead.');
  requestId = crypto.randomUUID(); displayJob(); await persist();
}
function clearResumes() {
  choices = []; $('resume').replaceChildren(new Option('Connect to load resumes', ''));
  $('account').textContent = 'Uses your HackerLeap login. No password is stored in this extension.';
  $('mode').textContent = ''; update();
}
async function loadResumes(type='resumes') {
  const data = await rpc(type);
  choices = data.resumes;
  $('resume').replaceChildren(new Option(choices.length ? 'Choose a saved resume' : 'No resumes yet — create one on HackerLeap', ''));
  choices.forEach((resume, i) => $('resume').append(new Option(resume.title + (resume.kind === 'draft' ? ` (revision ${resume.revision})` : ''), String(i))));
  const previous = choices.findIndex(r => `${r.kind}:${r.id}` === selectedId);
  if (previous >= 0) $('resume').value = String(previous);
  $('account').textContent = `Connected as ${data.account}`;
  $('mode').textContent = data.mode === 'chatgpt' ? 'Analysis runs in the background and uses your AI allowance.' : 'Manual mode: HackerLeap will prepare a prompt for your preferred AI tool.';
  update();
}
function run(action) {
  return async () => {
    if (busy) return;
    busy=true; update(); status('Working…');
    try {await action();} catch (error) {status(error.message, true);}
    finally {busy=false; update();}
  };
}
$('copy').addEventListener('click', run(async () => {await navigator.clipboard.writeText($('description').value); status('Job description copied.');}));
$('extract').addEventListener('click', run(async () => {await extract(); status('Description refreshed.');}));
$('connect').addEventListener('click', async () => {
  // Permission requests must originate directly from the user gesture.
  const granted = await chrome.permissions.request({origins: [permissionPattern(origin())]});
  if (!granted) {status('HackerLeap access was not granted. Copying descriptions still works.', true); return;}
  await run(async () => {await loadResumes('connect'); status('Connected. Choose your resume.');})();
});
$('reload').addEventListener('click', run(async () => {await loadResumes(); status('Resume list refreshed.');}));
$('disconnect').addEventListener('click', run(async () => {
  await chrome.permissions.remove({origins: [permissionPattern(origin())]});
  clearResumes(); selectedId=''; await persist(); status('Extension disconnected. Your HackerLeap website session remains signed in.');
}));
$('origin').addEventListener('change', run(async () => {
  clearResumes(); selectedId=''; requestId=crypto.randomUUID();
  await chrome.storage.local.set({origin: origin()}); await persist(); status('Click Connect for this environment.');
}));
for (const id of ['job-title', 'company', 'description']) $(id).addEventListener('input', () => {
  syncJob(); requestId=crypto.randomUUID(); update(); persist().catch(() => status('Unable to retain your edits. Keep this popup open.', true));
});
$('resume').addEventListener('change', () => {
  const choice = choices[Number($('resume').value)];
  selectedId = $('resume').value && choice ? `${choice.kind}:${choice.id}` : '';
  requestId=crypto.randomUUID(); update(); persist();
});
$('analyze').addEventListener('click', run(async () => {
  syncJob();
  const choice = choices[Number($('resume').value)];
  if (!choice || !$('resume').value || !job.description.trim() || job.description.length > 12000) throw new Error('Choose a resume and enter a description under 12,000 characters.');
  await persist();
  const {warning, ...payload} = job;
  const result = await rpc('submit', {selection: choice.selection, request_id: requestId, job: payload});
  status(result.status === 'queued' ? 'Analysis queued. Its progress page has opened.' : 'Your analysis page has opened.');
}));
async function initialize() {
  const settings = await chrome.storage.local.get('origin');
  try {$('origin').value = allowedOrigin(settings.origin || DEFAULT_ORIGIN);} catch (_) {$('origin').value = DEFAULT_ORIGIN;}
  [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  stateKey = `job:${tab?.id || 'manual'}`;
  const stored = await chrome.storage.session.get([stateKey, 'lastAnalysis']);
  const state = stored[stateKey];
  if (state && state.tabUrl === tab?.url && state.job?.description?.trim()) {
    job=state.job; requestId=state.requestId; selectedId=state.origin === origin() ? state.selectedId : '';
    displayJob();
  } else {
    try {await extract();} catch (_) {displayJob(); status('This page cannot be read. Paste a description or open a supported job page.', true);}
  }
  const last = stored.lastAnalysis;
  if (last) {
    try {
      const url = new URL(last.url); allowedOrigin(url.origin);
      if (/^\/app\/analysis\/[0-9a-f-]{36}\/$/.test(url.pathname)) {$('last-analysis').href=url.href; $('last-analysis').hidden=false;}
    } catch (_) { /* Ignore invalid local state. */ }
  }
  if (await chrome.permissions.contains({origins: [permissionPattern(origin())]})) {
    try {await loadResumes();} catch (error) {status(error.message, true);}
  }
}
initialize().catch(error => status(error.message, true));
