(() => {
  'use strict';
  const root = document.getElementById('pdf-job');
  if (!root) return;
  const label = document.getElementById('pdf-job-status');
  const ready = document.getElementById('pdf-ready');
  const retry = document.getElementById('pdf-check');
  let timer, navigated = false;
  async function check() {
    clearTimeout(timer);
    retry.hidden = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(root.dataset.status, {credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
      if (response.redirected || !response.ok) throw new Error('Unable to check this PDF. Your session may have expired.');
      const data = await response.json();
      if (data.status === 'ready') {
        label.textContent = 'Your PDF is ready.';
        ready.hidden = false;
        if (!navigated) { navigated = true; window.location.assign(root.dataset.file); }
      } else if (data.status === 'failed' || data.status === 'expired') {
        label.textContent = data.status === 'expired' ? 'This PDF has expired. Request a new export.' : data.error;
      } else {
        label.textContent = data.status === 'queued' ? 'PDF queued. Waiting for a worker…' : 'Generating your PDF…';
        timer = setTimeout(check, 2000);
      }
    } catch (error) {
      label.textContent = error.name === 'AbortError' ? 'Status check timed out. Check again.' : error.message;
      retry.hidden = false;
    } finally { clearTimeout(timeout); }
  }
  retry.addEventListener('click', check);
  window.addEventListener('pagehide', () => clearTimeout(timer));
  check();
})();
