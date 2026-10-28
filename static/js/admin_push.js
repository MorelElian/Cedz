(() => {
  const app = document.querySelector('[data-admin-app]');
  const form = app?.querySelector('[data-admin-push-form]');
  if (!app || !form) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const list = app.querySelector('[data-push-recipient-list]');
  const all = form.querySelector('[data-push-select-all]');
  const count = app.querySelector('[data-push-enabled-count]');
  const status = form.querySelector('[data-admin-push-status]');
  const result = app.querySelector('[data-admin-push-result]');
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  async function api(path, options = {}) {
    const response = await fetch(path, { ...options, headers: {'Accept':'application/json', ...(options.body ? {'Content-Type':'application/json'} : {}), ...(options.method && options.method !== 'GET' ? {'X-CSRF-Token':csrf} : {})} });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Opération impossible.');
    return data;
  }
  function selected() { return [...list.querySelectorAll('input[type="checkbox"]:checked')].map(input => Number(input.value)); }
  function render(people) {
    const enabled = people.filter(person => person.notificationsEnabled && person.isActive);
    count.textContent = `${enabled.length} actif${enabled.length > 1 ? 's' : ''}`;
    list.innerHTML = people.map(person => `<label class="push-recipient${person.notificationsEnabled && person.isActive ? '' : ' is-unavailable'}"><input type="checkbox" value="${esc(person.participantId)}" ${person.notificationsEnabled && person.isActive ? '' : 'disabled'}><span><strong>${esc(person.participant)}</strong><small>${person.notificationsEnabled ? `${esc(person.subscriptionCount)} appareil${person.subscriptionCount > 1 ? 's' : ''} abonné${person.subscriptionCount > 1 ? 's' : ''}` : 'Notifications non activées'}${person.isActive ? '' : ' · Compte en pause'}</small></span><span class="badge ${person.notificationsEnabled ? 'badge-active' : 'badge-inactive'}">${person.notificationsEnabled ? 'Prêt' : '—'}</span></label>`).join('') || '<div class="empty-state compact-empty"><strong>Aucun participant.</strong></div>';
  }
  async function load() { try { render((await api('/api/admin/push-subscriptions')).participants || []); } catch (error) { list.textContent = error.message; } }
  all.addEventListener('change', () => list.querySelectorAll('input:not(:disabled)').forEach(input => { input.checked = all.checked; }));
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (!form.reportValidity()) return;
    const participantIds = selected(); if (!participantIds.length) { status.textContent = 'Sélectionne au moins un participant abonné.'; return; }
    const button = form.querySelector('[type="submit"]'); button.disabled = true; status.textContent = 'Envoi…'; result.hidden = true;
    try {
      const data = new FormData(form); const payload = await api('/api/admin/push-notifications', {method:'POST', body:JSON.stringify({participantIds, title:data.get('title'), body:data.get('body'), url:data.get('url')})});
      const names = items => items.map(item => esc(item.participant)).join(', ') || 'personne';
      result.innerHTML = `<h2>Bilan de l’envoi</h2><p><strong>Envoyées :</strong> ${names(payload.sent || [])}</p><p><strong>Échecs :</strong> ${names(payload.failed || [])}</p><p><strong>Ignorées :</strong> ${names(payload.skipped || [])}</p>`;
      result.hidden = false; status.textContent = `${(payload.sent || []).length} notification(s) envoyée(s).`; await load();
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
  load();
})();
