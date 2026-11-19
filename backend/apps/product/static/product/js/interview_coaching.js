(function () {
    'use strict';
    var source = document.getElementById('interview-coaching-prompt');
    if (!source) return;
    var prompt = JSON.parse(source.textContent);
    var status = document.querySelector('[data-coaching-status]');
    var fallback = document.querySelector('[data-coaching-fallback]');
    var text = document.getElementById('coaching-text');

    async function copyPrompt() {
        try {
            await navigator.clipboard.writeText(prompt);
            return true;
        } catch (error) {
            // Keep all text available even when clipboard permissions are denied.
            text.closest('details').open = true;
            text.focus();
            text.select();
            return false;
        }
    }

    document.querySelector('[data-open-coaching]').addEventListener('click', async function () {
        var url = 'https://chatgpt.com/?q=' + encodeURIComponent(prompt);
        // Prefill is best-effort, not a guaranteed ChatGPT API contract. Never truncate.
        var prefill = url.length <= 6000;
        if (!prefill) url = 'https://chatgpt.com/';
        // Open synchronously within the click, before waiting for clipboard permission.
        var copying = copyPrompt();
        var tab = window.open('about:blank', '_blank');
        if (tab) {
            tab.opener = null;
            var meta = tab.document.createElement('meta');
            meta.name = 'referrer';
            meta.content = 'no-referrer';
            tab.document.head.appendChild(meta);
        }
        var copied = await copying;
        if (tab && !tab.closed) {
            tab.location.replace(url);
        } else {
            tab = null;
        }
        fallback.hidden = false;
        status.textContent = (tab ? 'ChatGPT opened. ' : 'Your browser blocked the new tab. Use the Open ChatGPT link below. ') +
            (copied ? (prefill ? 'The full prompt is also copied. If it is not prefilled, paste it into the new chat.' : 'The full prompt is copied. Paste it into the new chat, or attach the downloaded text file.') : 'Clipboard access was unavailable. Copy the selected prompt manually or download it, then paste or attach it in ChatGPT.');
    });
    document.querySelector('[data-copy-coaching]').addEventListener('click', async function () {
        status.textContent = await copyPrompt() ? 'Full coaching prompt copied.' : 'Copy the selected prompt manually, or download it as a text file.';
    });
    document.querySelector('[data-download-coaching]').addEventListener('click', function () {
        var url = URL.createObjectURL(new Blob([prompt], {type: 'text/plain;charset=utf-8'}));
        var link = document.createElement('a');
        link.href = url;
        link.download = 'interview-coaching.txt';
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
        status.textContent = 'Prompt downloaded. You can attach this file to a new ChatGPT chat.';
    });
})();
