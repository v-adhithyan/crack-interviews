(() => {
  document.querySelectorAll('[data-use-resume]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!window.confirm('Replace the resume currently selected for analysis with this saved draft?')) {
        event.preventDefault();
      }
    });
  });
  document.querySelectorAll('.rb-delete-menu').forEach(menu => {
    menu.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        menu.open = false;
        menu.querySelector('summary').focus();
      }
    });
  });
})();
