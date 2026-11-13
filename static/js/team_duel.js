(() => {
  const app = document.querySelector('[data-team-duel-app]');
  if (!app) return;

  const status = app.querySelector('[data-team-duel-status]');
  const retry = app.querySelector('[data-team-duel-retry]');
  const disciplines = app.querySelector('[data-team-duel-disciplines]');
  const camps = [
    {id: 'ancien_gros', label: 'Anciens gros', style: 'gros'},
    {id: 'ancien_maigre', label: 'Anciens maigres', style: 'maigre'},
  ];
  const sports = [{id: 'swim', label: 'Nage', mark: '≈'}, {id: 'bike', label: 'Vélo', mark: '↗'}, {id: 'run', label: 'Course', mark: '→'}];
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[char]));
  const hasValue = value => typeof value === 'number' && Number.isFinite(value);
  const number = value => hasValue(value) ? value.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '—';
  const count = value => Number.isInteger(value) && value >= 0 ? value : 0;
  const opinions = value => `${count(value)} avis révélé${count(value) > 1 ? 's' : ''}`;
  let loading = false;

  function trend(item, sport) {
    const history = Array.isArray(item.history) ? item.history : [];
    const values = history.flatMap(point => camps.map(camp => point.teams?.[camp.id])).filter(hasValue);
    if (!values.length) return '<p class="team-duel-empty">La tendance apparaîtra avec les premiers classements révélés.</p>';
    const low = Math.max(1, Math.floor(Math.min(...values)));
    const high = Math.max(low + 1, Math.ceil(Math.max(...values)));
    const x = index => history.length === 1 ? 300 : 44 + index * 512 / (history.length - 1);
    const y = value => 28 + (value - low) * 130 / (high - low);
    // A missing mean ends a segment: never draw an invented value for a camp.
    const lines = camps.map(camp => {
      let connected = false;
      const path = history.map((point, index) => {
        const value = point.teams?.[camp.id];
        if (!hasValue(value)) { connected = false; return ''; }
        const command = connected ? 'L' : 'M';
        connected = true;
        return `${command}${x(index)},${y(value)}`;
      }).join(' ');
      const dots = history.map((point, index) => {
        const value = point.teams?.[camp.id];
        return hasValue(value) ? `<circle cx="${x(index)}" cy="${y(value)}" r="4"><title>${esc(camp.label)} · ${esc(point.week)} : ${number(value)}</title></circle>` : '';
      }).join('');
      return `<g class="team-duel-line-${camp.style}"><path d="${path}"/>${dots}</g>`;
    }).join('');
    const description = history.map(point => `${point.week} : ${camps.map(camp => `${camp.label} ${number(point.teams?.[camp.id])}`).join(', ')}`).join(' ; ');
    return `<figure class="team-duel-trend"><figcaption>Moyenne cumulative par semaine <small>Plus haut = meilleure position</small></figcaption>
      <svg viewBox="0 0 600 200" role="img" aria-labelledby="duel-trend-${sport.id}-title duel-trend-${sport.id}-desc">
        <title id="duel-trend-${sport.id}-title">Tendance en ${sport.label.toLowerCase()}</title><desc id="duel-trend-${sport.id}-desc">${esc(description)}</desc>
        <path class="team-duel-gridline" d="M44,28 H556 M44,93 H556 M44,158 H556"/>
        <g class="team-duel-axis"><text x="30" y="32" text-anchor="end">${low}</text><text x="30" y="162" text-anchor="end">${high}</text>
        <text x="44" y="188">${esc(history[0].week)}</text>${history.length > 1 ? `<text x="556" y="188" text-anchor="end">${esc(history[history.length - 1].week)}</text>` : ''}</g>${lines}
      </svg><div class="team-duel-legend">${camps.map(camp => `<span class="team-duel-key-${camp.style}">${camp.label}</span>`).join('')}</div></figure>`;
  }

  function teamDetails(stats, camp) {
    const positions = Array.isArray(stats.positions) ? stats.positions : [];
    return `<section class="team-duel-team-details team-duel-${camp.style}"><h4>${camp.label}</h4>
      <dl class="team-duel-stat-list"><div><dt>Écart-type</dt><dd>± ${number(stats.stddev)}</dd></div><div><dt>Avis révélés</dt><dd>${count(stats.revealedCount)}</dd></div></dl>
      ${positions.length ? `<ul class="team-duel-positions">${positions.map(entry => `<li><span><strong>${esc(entry.participant?.displayName || 'Participant')}</strong><small>Avis de ${esc(entry.author?.displayName || 'un participant')}</small></span><b>${number(entry.position)}<small> position</small></b></li>`).join('')}</ul>` : '<p class="team-duel-empty">Aucun avis révélé pour cette équipe.</p>'}</section>`;
  }

  function discipline(item, sport) {
    const pending = count(item.pendingCount);
    const teams = item.teams || {};
    const comparable = camps.every(camp => hasValue(teams[camp.id]?.averagePosition));
    const winner = camps.find(camp => camp.id === item.winner);
    const verdict = !comparable ? 'Duel en attente' : item.winner === 'tie' ? 'Égalité' : winner ? `${winner.label} devant` : 'Comparaison en cours';
    const provisional = pending > 0 || item.isComplete === false;
    const mean = camp => `<span class="team-duel-mean team-duel-${camp.style}${winner?.id === camp.id ? ' is-leading' : ''}"><small>${camp.label}</small><strong>${number(teams[camp.id]?.averagePosition)}</strong><span>position moyenne</span></span>`;
    return `<details class="team-duel-discipline"><summary>
      <span class="team-duel-sport"><span class="team-duel-sport-mark" aria-hidden="true">${sport.mark}</span><span><strong>${sport.label}</strong><small>${opinions(item.revealedCount)}${provisional ? ' · Provisoire' : ''}</small></span></span>
      <span class="team-duel-comparison">${mean(camps[0])}<span class="team-duel-delta"><strong>${comparable && hasValue(item.delta) ? `+ ${number(item.delta)}` : '—'}</strong><small>écart</small></span>${mean(camps[1])}</span>
      <span class="team-duel-verdict">${verdict}<span class="team-duel-expand" aria-hidden="true">+</span></span>
      </summary><div class="team-duel-detail-body"><p class="team-duel-completeness">${opinions(item.revealedCount)} · ${pending} classement${pending > 1 ? 's' : ''} en attente.${provisional ? ' Le duel reste provisoire.' : ''}${!comparable ? ' Il faut un avis révélé dans chaque camp pour comparer.' : ''}</p>
      <div class="team-duel-details-grid">${camps.map(camp => teamDetails(teams[camp.id] || {}, camp)).join('')}</div>${trend(item, sport)}</div></details>`;
  }

  function render(payload) {
    const teams = Array.isArray(payload.teams) ? payload.teams : [];
    camps.forEach(camp => {
      const members = teams.find(team => team.id === camp.id)?.members || [];
      app.querySelector(`[data-team-duel-members="${camp.id}"]`).textContent = members.length ? members.map(person => person.displayName).join(' · ') : 'Aucun membre attribué';
    });
    const items = Array.isArray(payload.disciplines) ? payload.disciplines : [];
    const revealed = items.reduce((total, item) => total + count(item.revealedCount), 0);
    const pending = items.reduce((total, item) => total + count(item.pendingCount), 0);
    status.textContent = !revealed ? 'Le match attend ses premiers classements révélés.' : pending ? 'Duel provisoire : des classements attendent encore leur révélation.' : 'Le duel est à jour avec tous les classements révélés.';
    disciplines.innerHTML = sports.map(sport => discipline(items.find(item => item.id === sport.id) || {}, sport)).join('');
  }

  async function load() {
    if (loading) return;
    loading = true;
    retry.hidden = true;
    app.setAttribute('aria-busy', 'true');
    status.textContent = 'Chargement du duel…';
    try {
      const response = await fetch('/api/team-duel', {headers: {'Accept': 'application/json'}});
      if (response.status === 401) { window.location.assign('/login'); throw new Error('Session expirée. Reconnecte-toi pour voir le duel.'); }
      if (!response.ok) throw new Error('Impossible de charger le duel. Réessaie dans un instant.');
      const payload = await response.json();
      render(payload.data || payload);
      status.classList.remove('is-error');
    } catch (error) {
      status.textContent = error.message || 'Impossible de charger le duel.';
      status.classList.add('is-error');
      // Retain the camps, but hide stale results when a refresh fails.
      disciplines.replaceChildren();
      retry.hidden = false;
    } finally {
      app.setAttribute('aria-busy', 'false');
      loading = false;
    }
  }

  function activate() { if (window.location.hash === '#team-duel') load(); }
  retry.addEventListener('click', load);
  window.addEventListener('hashchange', activate);
  activate();
})();
