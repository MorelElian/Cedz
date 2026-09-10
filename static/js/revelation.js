(() => {
  const app = document.querySelector('[data-revelation-detail]');
  if (!app) return;
  const id = app.dataset.revelationId;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const pick = (object, ...keys) => keys.map(key => object?.[key]).find(value => value !== undefined && value !== null);

  async function api(path, options = {}) {
    const headers = {'Accept':'application/json', ...(options.body ? {'Content-Type':'application/json'} : {}), ...options.headers};
    if (options.method && options.method !== 'GET' && csrf) headers['X-CSRF-Token'] = csrf;
    const response = await fetch(path, {...options, headers});
    if (response.status === 401) { window.location.assign('/login'); throw new Error('Session expirée.'); }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || payload.message || 'Impossible de charger cette révélation.');
    return payload.data || payload.revelation || payload;
  }

  function showReply(reply) {
    const form = app.querySelector('[data-reply-form]');
    const block = app.querySelector('[data-existing-reply]');
    form.hidden = true; block.hidden = false;
    block.textContent = pick(reply, 'message', 'content', 'text') || reply;
  }

  async function load() {
    try {
      const item = await api(`/api/account/revelations/${encodeURIComponent(id)}`);
      const author = item.author || item.authorParticipant || item.author_participant || {};
      const authorName = pick(item, 'authorName', 'author_name') || pick(author, 'displayName', 'display_name', 'name') || 'Inconnu';
      const avatar = pick(author, 'profilePhotoUrl', 'profile_photo_url', 'avatarUrl', 'avatar_url');
      app.querySelector('[data-author-avatar]').innerHTML = avatar ? `<img src="${esc(avatar)}" alt="">` : `<span>${esc(authorName.slice(0, 2).toUpperCase())}</span>`;
      app.querySelector('[data-author-name]').textContent = authorName;
      app.querySelector('[data-revelation-type]').textContent = pick(item, 'typeLabel', 'type_label', 'type') || 'Révélation';
      app.querySelector('[data-revelation-title]').textContent = pick(item, 'title', 'subject') || 'Le comité a parlé.';
      const question = pick(item, 'question', 'questionText', 'question_text');
      const content = pick(item, 'finalContent', 'final_content', 'content', 'body') || '—';
      app.querySelector('[data-revelation-body]').innerHTML = `${question ? `<p>${esc(question)}</p>` : ''}<blockquote>${esc(content)}</blockquote>`;
      const reply = item.reply || item.recipientReply || item.recipient_reply;
      if (reply) showReply(reply);
      app.querySelector('[data-detail-loading]').hidden = true;
      app.querySelector('[data-detail-content]').hidden = false;
    } catch (_) { app.querySelector('[data-detail-loading]').hidden = true; app.querySelector('[data-detail-error]').hidden = false; }
  }

  app.querySelector('[data-reply-form]').addEventListener('submit', async event => {
    event.preventDefault(); if (!event.currentTarget.reportValidity()) return;
    const message = event.currentTarget.elements.message.value.trim();
    const button = event.currentTarget.querySelector('button');
    const status = app.querySelector('[data-reply-status]');
    button.disabled = true; status.textContent = 'Envoi…';
    try { const payload = await api(`/api/account/revelations/${encodeURIComponent(id)}/reply`, {method:'POST', body:JSON.stringify({message})}); showReply(payload.reply || {message}); }
    catch (error) { status.textContent = error.message; button.disabled = false; }
  });

  load();
})();
