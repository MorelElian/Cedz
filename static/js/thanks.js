(() => {
  const form = document.querySelector('[data-feedback-form]');
  if (!form) return;

  const error = form.querySelector('[data-feedback-error]');
  const success = form.querySelector('[data-feedback-success]');
  const button = form.querySelector('button[type="submit"]');

  form.addEventListener('submit', async event => {
    event.preventDefault();
    error.hidden = true;
    success.hidden = true;
    const message = new FormData(form).get('message')?.trim();
    if (!message) {
      error.textContent = 'Écris un petit mot avant de l’envoyer.';
      error.hidden = false;
      return;
    }
    button.disabled = true;
    try {
      const response = await fetch(`/api/sessions/${encodeURIComponent(form.dataset.sessionId)}/feedback`, {
        method: 'POST',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
        body: JSON.stringify({message}),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || payload.message || 'Envoi impossible.');
      form.reset();
      success.hidden = false;
    } catch (reason) {
      error.textContent = reason.message;
      error.hidden = false;
    } finally {
      button.disabled = false;
    }
  });
})();
