(() => {
  const app = document.querySelector('[data-admin-app]');
  if (!app) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const root = app.querySelector('[data-daily-mail-preview]');
  const sendButton = app.querySelector('[data-send-daily-mail-batch]');
  const summary = app.querySelector('[data-daily-mail-send-summary]');
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  async function load() {
    root.innerHTML = '<div class="admin-card loading-row">Chargement des aperçus…</div>';
    try {
      const response = await fetch('/api/admin/daily-question-mail-preview', {headers: {Accept: 'application/json', 'X-CSRF-Token': csrf}});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || 'Impossible de charger les aperçus.');
      const previews = payload.previews || [];
      if (!previews.length) { root.innerHTML = '<div class="empty-state compact-empty"><strong>Pas encore de mail à prévisualiser.</strong><p>Les participants doivent d’abord terminer leur questionnaire.</p></div>'; return; }
      root.innerHTML = previews.map((item, index) => `<article class="admin-card daily-mail-preview-card"><header><strong>${esc(item.participantName)}</strong><small>${esc(item.recipientEmail || 'Adresse e-mail manquante')}</small></header><p><strong>Objet :</strong> ${esc(item.subject)}</p><div class="mail-preview-frame"><iframe title="Aperçu du mail pour ${esc(item.participantName)}" data-daily-mail-frame="${index}"></iframe></div></article>`).join('');
      previews.forEach((item, index) => { const frame = root.querySelector(`[data-daily-mail-frame="${index}"]`); if (frame) frame.srcdoc = item.html; });
    } catch (error) { root.innerHTML = `<div class="error-state"><strong>${esc(error.message)}</strong></div>`; }
  }
  app.querySelector('[data-tab="daily-mails"]')?.addEventListener('click', load);
  app.querySelector('[data-reload-daily-mail-preview]')?.addEventListener('click', load);
  sendButton?.addEventListener('click', async () => {
    if (!window.confirm('Envoyer maintenant les mails bonus non encore envoyés ?')) return;
    sendButton.disabled = true;
    sendButton.textContent = 'Envoi en cours…';
    summary.hidden = false;
    summary.textContent = 'Envoi de la volée…';
    try {
      const response = await fetch('/api/admin/daily-question-mails/send', {method: 'POST', headers: {Accept: 'application/json', 'X-CSRF-Token': csrf}});
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || 'L’envoi a échoué.');
      const sent = result.sent || [], failed = result.failed || [], skipped = result.skipped || [], alreadySent = result.alreadySent || [];
      const names = sent.map(item => item.participant).join(', ') || 'personne';
      const failedDetails = failed.map(item => `${item.participant} (${item.error || 'erreur inconnue'})`).join(', ');
      summary.innerHTML = `<strong>${sent.length} envoyé${sent.length > 1 ? 's' : ''}</strong> : ${esc(names)}.${failed.length ? ` <strong>${failed.length} échec${failed.length > 1 ? 's' : ''}</strong> : ${esc(failedDetails)}.` : ''}${skipped.length ? ` ${skipped.length} ignoré${skipped.length > 1 ? 's' : ''} (adresse ou question manquante).` : ''}${alreadySent.length ? ` ${alreadySent.length} déjà envoyé${alreadySent.length > 1 ? 's' : ''}.` : ''}`;
      await load();
    } catch (error) { summary.textContent = error.message; }
    finally { sendButton.disabled = false; sendButton.textContent = 'Envoyer la volée'; }
  });
  if (location.hash === '#daily-mails') load();
})();
