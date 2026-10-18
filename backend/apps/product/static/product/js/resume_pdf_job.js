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
      document.getElementById('pdf-progress-title').textContent = data.label;
      const failed = data.status === 'failed' || data.status === 'expired';
      root.classList.toggle('analysis-progress-card-failed', failed);
      document.getElementById('pdf-progress').hidden = failed;
      if (!failed) {
        const percent = Math.max(0, Math.min(100, data.progress || 0));
        const meter = document.getElementById('pdf-progress-meter');
        meter.setAttribute('aria-valuenow', String(percent));
        meter.setAttribute('aria-valuetext', data.stage);
        document.getElementById('pdf-progress-bar').style.width = `${percent}%`;
        document.getElementById('pdf-progress-percent').textContent = `${percent}%`;
        document.getElementById('pdf-progress-stage').textContent = data.stage;
      }
      if (data.status === 'ready') {
        label.textContent = 'Your PDF is ready.';
        ready.hidden = false;
        if (!navigated) { navigated = true; timer = setTimeout(() => window.location.assign(root.dataset.file), 500); }
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
