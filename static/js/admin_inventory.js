(() => {
  const root = document.querySelector('[data-revelation-inventory]');
  if (!root) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const peopleRoot = root.querySelector('[data-inventory-people]');
  const detailRoot = root.querySelector('[data-inventory-detail]');
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const date = value => value ? new Date(value).toLocaleString('fr-FR', {dateStyle:'medium', timeStyle:'short'}) : 'Date indisponible';
  let people = [];
  let selectedId = null;

  async function api(path) {
    const response = await fetch(path, {headers: {Accept:'application/json', 'X-CSRF-Token':csrf}});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(payload.error || 'Chargement impossible.');
    return payload;
  }

  function avatar(person) {
    return person.profilePhotoUrl ? `<img src="${esc(person.profilePhotoUrl)}" alt="">` : `<span>${esc(person.displayName.slice(0, 2))}</span>`;
  }

  function renderPeople() {
    peopleRoot.innerHTML = people.map(person => `<button type="button" class="inventory-person ${person.id === selectedId ? 'is-selected' : ''}" data-inventory-person="${person.id}"><span class="mini-avatar">${avatar(person)}</span><span><strong>${esc(person.displayName)}</strong><small><b>${person.sentCount}</b> envoyées · <b>${person.readyCount}</b> prêtes · <b>${person.remainingCount}</b> restantes</small></span></button>`).join('') || '<div class="empty-state">Aucun participant actif.</div>';
  }

  function card(item, sent) {
    const label = sent ? 'Envoyée' : item.status === 'in_review' ? 'Prête à envoyer' : 'Dans le pool';
    const timestamp = sent ? item.sentAt : item.createdAt;
    const content = sent ? item.finalContent : item.answerSummary;
    return `<article class="inventory-card ${sent ? 'is-sent' : `is-${esc(item.status)}`} "><header><span class="badge ${sent ? 'badge-active' : 'badge-inactive'}">${label}</span><time>${esc(date(timestamp))}</time></header><p class="inventory-question">${esc(item.question)}</p><p class="inventory-author">Réponse de <strong>${esc(item.authorName)}</strong></p><blockquote>${esc(content || 'Réponse indisponible.')}</blockquote></article>`;
  }

  function renderDetail(data) {
    const sent = data.sent || [];
    const remaining = data.remaining || [];
    detailRoot.innerHTML = `<header class="inventory-head"><span class="mini-avatar">${avatar(data.participant)}</span><div><p class="eyebrow">Dossier individuel</p><h2>${esc(data.participant.displayName)}</h2></div><div class="inventory-totals"><span><b>${sent.length}</b> envoyées</span><span><b>${remaining.filter(item => item.status === 'in_review').length}</b> prêtes</span><span><b>${remaining.filter(item => item.status === 'candidate').length}</b> restantes</span></div></header><div class="inventory-columns"><section><header class="inventory-column-head"><h3>Déjà révélées</h3><span>${sent.length}</span></header><div class="inventory-card-list">${sent.map(item => card(item, true)).join('') || '<p class="inventory-empty">Aucune révélation envoyée pour le moment.</p>'}</div></section><section><header class="inventory-column-head"><h3>À révéler</h3><span>${remaining.length}</span></header><div class="inventory-card-list">${remaining.map(item => card(item, false)).join('') || '<p class="inventory-empty">Le pool est vide.</p>'}</div></section></div>`;
  }

  async function loadPerson(id) {
    selectedId = Number(id);
    renderPeople();
    detailRoot.innerHTML = '<div class="admin-card loading-row">Chargement du dossier…</div>';
    try { renderDetail(await api(`/api/admin/revelation-inventory/${selectedId}`)); }
    catch (error) { detailRoot.innerHTML = `<div class="admin-card error-state"><strong>Dossier indisponible.</strong><p>${esc(error.message)}</p></div>`; }
  }

  async function load() {
    try {
      const data = await api('/api/admin/revelation-inventory');
      people = data.participants || [];
      if (!people.some(person => person.id === selectedId)) selectedId = people[0]?.id || null;
      renderPeople();
      if (selectedId) await loadPerson(selectedId);
      else detailRoot.innerHTML = '<div class="admin-card empty-state">Aucun participant actif.</div>';
    } catch (error) { peopleRoot.innerHTML = `<div class="error-state">${esc(error.message)}</div>`; }
  }

  peopleRoot.addEventListener('click', event => {
    const button = event.target.closest('[data-inventory-person]');
    if (button) loadPerson(button.dataset.inventoryPerson);
  });
  window.addEventListener('cedz:answers-imported', load);
  load();
})();
