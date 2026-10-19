(() => {
  'use strict';
  const questions = document.getElementById('followup-questions');
  const add = document.getElementById('add-question');
  function update() {
    const rows = questions.querySelectorAll('.followup-question');
    rows.forEach((row, i) => {
      row.querySelector('[data-number]').textContent = i + 1;
      row.querySelector('[data-remove]').disabled = rows.length === 1;
    });
    add.disabled = rows.length >= 10;
    document.getElementById('question-count').textContent = `${rows.length} of 10 questions`;
  }
  if (questions) {
    questions.addEventListener('click', event => {
      if (event.target.matches('[data-remove]') && questions.children.length > 1) {
        event.target.closest('.followup-question').remove(); update();
      }
    });
    add.addEventListener('click', () => {
      if (questions.children.length >= 10) return;
      const row = questions.firstElementChild.cloneNode(true);
      row.querySelector('textarea').value = '';
      questions.append(row); update(); row.querySelector('textarea').focus();
    });
    update();
    document.getElementById('followup-form').addEventListener('submit', event => {
      event.target.querySelector('[type=submit]').disabled = true;
    });
  }
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    const source = document.getElementById(button.dataset.copy);
    const text = source.tagName === 'TEXTAREA' ? source.value : source.textContent;
    const status = document.getElementById('copy-status');
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else {
        const area = document.createElement('textarea'); area.value = text;
        document.body.append(area); area.select();
        const copied = document.execCommand('copy'); area.remove();
        if (!copied) throw new Error('Copy failed');
      }
      status.textContent = 'Copied to clipboard.';
      const label = button.textContent; button.textContent = 'Copied';
      setTimeout(() => {button.textContent = label;}, 1500);
    } catch (_) {status.textContent = 'Unable to copy automatically. Select the text and copy it manually.';}
  }));
  const progress = document.querySelector('[data-followup-status]');
  if (progress) {
    let failures = 0;
    async function poll() {
      try {
        const response = await fetch(progress.dataset.followupStatus, {credentials: 'same-origin'});
        if (!response.ok || response.redirected) throw new Error('Status unavailable');
        const data = await response.json();
        if (!['queued', 'processing'].includes(data.status)) {window.location.reload(); return;}
        failures = 0;
        document.getElementById('followup-progress').textContent = data.status === 'queued' ? 'Queued — waiting for an AI worker.' : 'Generating your answers…';
      } catch (_) {
        failures++;
        document.getElementById('followup-progress').textContent = 'Unable to check progress. Refresh this page to try again.';
      }
      if (failures < 5) setTimeout(poll, 2500);
    }
    setTimeout(poll, 1500);
  }
})();
