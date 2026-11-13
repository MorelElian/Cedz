(() => {
  const root = document.querySelector('[data-admin-team-duel]');
  if (!root) return;

  const assignments = root.querySelector('[data-admin-team-duel-assignments]');
  const summary = root.querySelector('[data-admin-team-duel-summary]');
  const status = root.querySelector('[data-admin-team-duel-status]');
  const errorBox = root.querySelector('[data-admin-team-duel-error]');
  const reload = root.querySelector('[data-admin-team-duel-reload]');
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const camps = [{id: 'ancien_gros', label: 'Anciens gros'}, {id: 'ancien_maigre', label: 'Anciens maigres'}, {id: '', label: 'Non attribué'}];
  const sports = [{id: 'swim', label: 'Nage'}, {id: 'bike', label: 'Vélo'}, {id: 'run', label: 'Course'}];
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[char]));
  const number = value => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '—';
  let state = null;
  let busy = false;

  async function api(path, options = {}) {
    const response = await fetch(path, {...options, headers: {Accept: 'application/json', ...(options.body ? {'Content-Type': 'application/json', 'X-CSRF-Token': csrf} : {})}});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || 'Opération impossible. Réessaie dans un instant.');
    return payload;
  }

  function setBusy(value) {
    busy = value;
    root.setAttribute('aria-busy', String(value));
    reload.disabled = value;
    assignments.querySelectorAll('select').forEach(select => { select.disabled = value; });
  }

  function showError(error) {
    errorBox.textContent = error.message || 'Le duel est indisponible.';
    errorBox.hidden = false;
  }

  function render(payload) {
    state = payload;
    const people = payload.participants || [];
    assignments.innerHTML = camps.map(camp => {
      const members = people.filter(person => (person.team || '') === camp.id);
      return `<section class="admin-team-duel-group"><h4>${camp.label} <span>${members.length}</span></h4>${members.map(person => `<label class="admin-team-duel-person" for="team-duel-person-${esc(person.id)}"><span><strong>${esc(person.displayName)}</strong><small>Camp de ${esc(person.displayName)}${person.isActive ? '' : ' · Inactif'}</small></span><select id="team-duel-person-${esc(person.id)}" data-team-duel-person="${esc(person.id)}">${camps.map(option => `<option value="${option.id}"${option.id === (person.team || '') ? ' selected' : ''}>${option.label}</option>`).join('')}</select></label>`).join('') || '<p class="admin-team-duel-note">Aucun participant dans ce camp.</p>'}</section>`;
    }).join('');

    const disciplines = payload.disciplines || [];
    summary.innerHTML = `<div class="admin-team-duel-table"><table><caption class="sr-only">Positions moyennes par équipe et discipline</caption><thead><tr><th scope="col">Discipline</th><th scope="col">Anciens gros</th><th scope="col">Anciens maigres</th><th scope="col">Écart</th></tr></thead><tbody>${sports.map(sport => {
      const item = disciplines.find(discipline => discipline.id === sport.id) || {};
      const winner = camps.find(camp => camp.id === item.winner);
      const verdict = item.winner === 'tie' ? 'Égalité' : winner ? `${winner.label} devant` : 'Duel en attente';
      return `<tr><th scope="row">${sport.label}</th><td>${number(item.teams?.ancien_gros?.averagePosition)}</td><td>${number(item.teams?.ancien_maigre?.averagePosition)}</td><td>${typeof item.delta === 'number' ? `+ ${number(item.delta)}` : '—'}</td></tr><tr class="admin-team-duel-context"><td colspan="4">${verdict} · ${item.revealedCount || 0} avis révélés · ${item.pendingCount || 0} en attente${item.pendingCount > 0 || item.isComplete === false ? ' · Provisoire' : ''}</td></tr>`;
    }).join('')}</tbody></table></div>`;
    const hasRevealed = disciplines.some(item => item.revealedCount > 0);
    status.textContent = !hasRevealed ? 'Le duel attend ses premiers classements révélés.' : disciplines.some(item => item.pendingCount > 0) ? 'Duel provisoire : des classements attendent encore leur révélation.' : 'Le duel est à jour.';
    errorBox.hidden = true;
  }

  async function load() {
    if (busy) return;
    setBusy(true);
    status.textContent = 'Chargement du duel…';
    try { render(await api('/api/admin/team-duel')); }
    catch (error) {
      status.textContent = state ? 'Les dernières données chargées restent affichées.' : 'Le duel n’a pas pu être chargé.';
      showError(error);
    } finally { setBusy(false); }
  }

  assignments.addEventListener('change', async event => {
    const select = event.target.closest('[data-team-duel-person]');
    if (!select || busy) return;
    const person = state?.participants.find(person => String(person.id) === select.dataset.teamDuelPerson);
    if (!person) return;
    const focusId = select.id;
    const team = select.value || null;
    setBusy(true);
    status.textContent = 'Enregistrement du camp…';
    try {
      render(await api(`/api/admin/team-duel/participants/${encodeURIComponent(person.id)}`, {method: 'PATCH', body: JSON.stringify({team})}));
      status.textContent = `Camp de ${person.displayName} enregistré. Le duel a été recalculé.`;
    } catch (error) {
      select.value = person.team || '';
      status.textContent = 'La modification n’a pas été enregistrée. Le camp précédent reste affiché.';
      showError(error);
    } finally {
      setBusy(false);
      document.getElementById(focusId)?.focus();
    }
  });

  reload.addEventListener('click', load);
  // Observe the existing tab controller, including direct #team-duel visits.
  new MutationObserver(() => { if (!root.hidden) load(); }).observe(root, {attributes: true, attributeFilter: ['hidden']});
  window.addEventListener('cedz:answers-imported', () => { if (!root.hidden) load(); });
  if (!root.hidden) load();
})();
