(() => {
  const app = document.querySelector('[data-start-app]');
  if (!app) return;

  const grid = app.querySelector('[data-participant-grid]');
  const form = app.querySelector('[data-session-form]');
  const error = app.querySelector('[data-form-error]');
  const submit = app.querySelector('[data-submit-session]');

  const initials = (name = '?') => name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
  const normalizeParticipant = participant => ({...participant, display_name: participant.display_name || participant.displayName, choice_photo_url: participant.choice_photo_url || participant.choicePhotoUrl || participant.avatar_url || participant.avatarUrl, is_active: participant.is_active ?? participant.isActive});
  const participantCard = rawParticipant => {
    const participant = normalizeParticipant(rawParticipant);
    const label = document.createElement('label');
    label.className = 'participant-card';
    const avatar = participant.choice_photo_url
      ? `<img src="${escapeHtml(participant.choice_photo_url)}" alt="" loading="lazy">`
      : `<span class="avatar-fallback" aria-hidden="true">${escapeHtml(initials(participant.display_name))}</span>`;
    label.innerHTML = `<input type="radio" name="participant_id" value="${escapeHtml(participant.id)}" data-requires-secret="${participant.requiresSecretCode ? 'true' : 'false'}" required>
      <span class="participant-visual">${avatar}</span>
      <span class="participant-name">${escapeHtml(participant.display_name)}</span>
      <span class="participant-select">C'est moi <span aria-hidden="true">→</span></span>`;
    return label;
  };

  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const unwrap = (payload, key) => Array.isArray(payload) ? payload : payload?.[key] || payload?.data?.[key] || payload?.data || [];

  async function loadParticipants() {
    if (grid.querySelector('.participant-card')) {
      grid.setAttribute('aria-busy', 'false');
      return;
    }
    try {
      const response = await fetch('/api/participants', {headers: {'Accept': 'application/json'}});
      if (!response.ok) throw new Error('participants');
      const participants = unwrap(await response.json(), 'participants').map(normalizeParticipant).filter(item => item.is_active !== false);
      grid.replaceChildren();
      if (!participants.length) {
        grid.innerHTML = '<div class="empty-state"><span aria-hidden="true">🏁</span><strong>La ligne de départ est encore vide.</strong><p>L’admin doit ajouter les participants avant le coup d’envoi.</p></div>';
      } else {
        participants.forEach(participant => grid.append(participantCard(participant)));
      }
    } catch (_) {
      grid.innerHTML = '<div class="error-state"><span aria-hidden="true">⚠</span><h3>Impossible d’appeler les athlètes.</h3><p>Recharge la page dans un instant.</p></div>';
    } finally {
      grid.setAttribute('aria-busy', 'false');
    }
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    error.hidden = true;
    if (!form.reportValidity()) return;
    const data = new FormData(form);
    const participantId = data.get('participant_id');
    const body = {
      participant_id: participantId, participantId,
      email: data.get('email'), phone: data.get('phone')
    };
    const resumeToken = localStorage.getItem(`cedz-resume-${participantId}`);
    if (resumeToken) body.resumeToken = resumeToken;
    if (data.get('secret_code')) body.secret_code = body.secretCode = data.get('secret_code');
    submit.disabled = true;
    submit.querySelector('span').textContent = 'Chargement…';
    try {
      const response = await fetch('/api/sessions', {
        method: 'POST', headers: {'Accept': 'application/json', 'Content-Type': 'application/json'}, body: JSON.stringify(body)
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || payload.message || 'Impossible de démarrer la session.');
      const session = payload.session || payload.data || payload;
      const sessionId = session.session_id || session.sessionId || session.id || payload.session_id || payload.sessionId;
      if (!sessionId) throw new Error('La session a été créée sans identifiant.');
      const newResumeToken = session.resumeToken || session.resume_token || payload.resumeToken || payload.resume_token;
      if (newResumeToken) localStorage.setItem(`cedz-resume-${participantId}`, newResumeToken);
      window.location.assign(session.questionnaire_url || session.questionnaireUrl || payload.redirect_url || payload.redirectUrl || `/questionnaire/${encodeURIComponent(sessionId)}`);
    } catch (reason) {
      error.textContent = reason.message || 'Un problème est survenu. Réessaie.';
      error.hidden = false;
      submit.disabled = false;
      submit.querySelector('span').textContent = "C'est parti";
    }
  });

  form.addEventListener('change', event => {
    if (event.target.name !== 'participant_id') return;
    const secretField = form.querySelector('[data-secret-field]');
    const secretInput = secretField.querySelector('input');
    const required = event.target.dataset.requiresSecret === 'true';
    secretField.hidden = !required;
    secretInput.required = required;
    if (!required) secretInput.value = '';
  });

  const intro = document.querySelector('[data-intro-overlay]');
  if (intro) {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const finishIntro = () => {
      intro.remove();
    };
    intro.addEventListener('animationend', event => {
      if (event.target === intro) finishIntro();
    });
    window.setTimeout(finishIntro, reducedMotion ? 20 : 1900);
  }
  loadParticipants();
})();
