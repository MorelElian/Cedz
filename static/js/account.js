(() => {
  const app = document.querySelector('[data-account-app]');
  if (!app) return;

  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const pick = (object, ...keys) => keys.map(key => object?.[key]).find(value => value !== undefined && value !== null);
  const list = (payload, key) => Array.isArray(payload) ? payload : payload?.[key] || payload?.data?.[key] || [];

  async function api(path, options = {}) {
    const headers = {'Accept': 'application/json', ...(options.body ? {'Content-Type': 'application/json'} : {}), ...options.headers};
    if (options.method && options.method !== 'GET' && csrf) headers['X-CSRF-Token'] = csrf;
    const response = await fetch(path, {...options, headers});
    if (response.status === 401) { window.location.assign('/login'); throw new Error('Session expirée.'); }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || payload.message || 'Impossible de charger ton espace.');
    return payload.data || payload;
  }

  function avatarMarkup(person, className = '') {
    const name = pick(person, 'displayName', 'display_name', 'name') || '?';
    const url = pick(person, 'profilePhotoUrl', 'profile_photo_url', 'avatarUrl', 'avatar_url');
    return url ? `<img class="${className}" src="${esc(url)}" alt="">` : `<span class="${className}">${esc(name.slice(0, 2).toUpperCase())}</span>`;
  }

  function revelationMarkup(item, featured = false) {
    if (!item) return '<div class="empty-state compact-empty"><strong>Rien pour le moment.</strong><p>Profite du calme.</p></div>';
    const author = pick(item, 'author', 'authorParticipant', 'author_participant') || {};
    const authorName = pick(item, 'authorName', 'author_name') || pick(author, 'displayName', 'display_name', 'name') || 'Inconnu';
    const question = pick(item, 'question', 'questionText', 'question_text', 'title') || 'Le comité a parlé';
    const content = pick(item, 'finalContent', 'final_content', 'content', 'body') || '—';
    const id = pick(item, 'id', 'revelationId', 'revelation_id');
    const date = pick(item, 'sentAt', 'sent_at', 'createdAt', 'created_at') || '';
    return `<article class="revelation-card${featured ? ' revelation-featured' : ''}">
      <header><span class="mini-avatar">${avatarMarkup(author)}</span><span><small>Par</small><strong>${esc(authorName)}</strong></span>${date ? `<time>${esc(formatDate(date))}</time>` : ''}</header>
      <p class="revelation-question">${esc(question)}</p><blockquote>${esc(content)}</blockquote>
      ${id ? `<a class="text-button" href="/revelations/${encodeURIComponent(id)}">Voir et répondre →</a>` : ''}
    </article>`;
  }

  function formatDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('fr-FR', {day:'numeric', month:'short', year:'numeric'}).format(date);
  }

  function renderRankings(rankings) {
    const labels = {swim:['Nage','≈'], bike:['Vélo','↗'], run:['Course','→']};
    const aliases = {swimming:'swim', cycling:'bike', running:'run', nage:'swim', velo:'bike', 'vélo':'bike', course:'run'};
    const normalized = {};
    if (Array.isArray(rankings)) rankings.forEach(item => { normalized[aliases[String(item.discipline).toLowerCase()] || item.discipline] = item; });
    else Object.entries(rankings || {}).forEach(([key, value]) => { normalized[aliases[key.toLowerCase()] || key] = typeof value === 'object' ? value : {averagePosition:value}; });
    app.querySelector('[data-rankings]').innerHTML = Object.entries(labels).map(([key, [label, mark]]) => {
      const item = normalized[key] || {}, value = pick(item, 'averagePosition', 'average_position', 'average', 'position');
      const count = Number(pick(item, 'revealedCount', 'revealed_count', 'count') || 0);
      return `<article class="discipline-card discipline-${key}"><span aria-hidden="true">${mark}</span><p>${label}</p><strong>${value ? `${Number(value).toLocaleString('fr-FR', {maximumFractionDigits:1})}<sup>e</sup>` : '—'}</strong><small>${count ? `${count} avis révélé${count > 1 ? 's' : ''}` : 'Pas encore de classement'}</small></article>`;
    }).join('');
  }

  function renderAnswers(answers, participantNames = {}) {
    const root = app.querySelector('[data-my-answers]');
    if (!answers.length) { root.innerHTML = '<div class="empty-state compact-empty"><strong>Aucune réponse.</strong></div>'; return; }
    const groups = answers.reduce((result, answer) => {
      const category = pick(answer, 'category', 'questionCategory', 'question_category') || 'Autres';
      (result[category] ||= []).push(answer); return result;
    }, {});
    root.innerHTML = Object.entries(groups).sort(([a], [b]) => a.localeCompare(b, 'fr')).map(([category, items]) => `<details class="answer-group"><summary><span>${esc(category)}</span><small>${items.length} réponse${items.length > 1 ? 's' : ''}</small></summary><div>${items.map(item => {
      const question = pick(item, 'renderedQuestion', 'rendered_question', 'question', 'questionText', 'question_text') || 'Question';
      let answer = pick(item, 'displayAnswer', 'display_answer', 'answerText', 'answer_text', 'answerNumber', 'answer_number', 'answer', 'answerJson', 'answer_json');
      if (typeof answer === 'object') {
        const name = id => participantNames[String(id)] || `#${id}`;
        if (answer.selected_participant_id) answer = name(answer.selected_participant_id) + (answer.comment ? ` — ${answer.comment}` : '');
        else if (answer.ordered_participant_ids) answer = answer.ordered_participant_ids.map((id, index) => `${index + 1}. ${name(id)}`).join(' · ');
        else if (answer.category_a || answer.category_b) answer = `Groupe A : ${(answer.category_a || []).map(name).join(', ')} · Groupe B : ${(answer.category_b || []).map(name).join(', ')}`;
        else answer = pick(answer, 'display', 'label', 'text') || JSON.stringify(answer);
      }
      return `<article><p>${esc(question)}</p><strong>${esc(answer ?? '—')}</strong></article>`;
    }).join('')}</div></details>`).join('');
  }

  function renderReplies(replies) {
    const root = app.querySelector('[data-replies-received]');
    if (!replies.length) { root.innerHTML = '<div class="empty-state compact-empty"><strong>Aucun retour pour l’instant.</strong><p>Ils cherchent sûrement leurs mots.</p></div>'; return; }
    root.innerHTML = replies.map(reply => {
      const sender = pick(reply, 'from_participant', 'fromParticipant', 'authorName', 'author_name') || 'Un participant';
      const question = pick(reply, 'original_question', 'originalQuestion') || '';
      const original = pick(reply, 'original_message', 'originalMessage') || '';
      return `<article class="received-reply"><header><strong>${esc(sender)}</strong><time>${esc(formatDate(pick(reply, 'created_at', 'createdAt') || ''))}</time></header>
        <div class="reply-context"><small>Ton message auquel ${esc(sender)} répond</small>${question ? `<p>${esc(question)}</p>` : ''}<div>${esc(original || 'Message d’origine indisponible.')}</div></div>
        <small class="reply-answer-label">Sa réponse</small><blockquote>${esc(pick(reply, 'message', 'content') || '—')}</blockquote></article>`;
    }).join('');
  }

  function renderDaily(question) {
    const section=app.querySelector('[data-daily-section]'),root=app.querySelector('[data-daily-question]');
    section.hidden=false;
    if(!question){root.innerHTML='<div class="empty-state compact-empty"><strong>On recharge les munitions.</strong><p>Reviens demain pour une nouvelle question.</p></div>';return;}
    const type=pick(question,'type'),id=pick(question,'id'),body=pick(question,'body')||'Question';
    let input='';
    if(type==='slider') input='<input name="answer" type="range" min="'+esc(question.scaleMin??0)+'" max="'+esc(question.scaleMax??100)+'" value="'+esc(question.scaleMin??0)+'"><output>'+esc(question.scaleMin??0)+'</output>';
    else if(type==='compare_two'||type==='compare_three'||type==='choose_one') input='<div class="daily-choices">'+(question.targets||[]).map(person=>'<label><input type="radio" name="answer" value="'+esc(person.id)+'" required>'+esc(person.displayName)+'</label>').join('')+'</div><textarea name="comment" placeholder="Un commentaire (facultatif)"></textarea>';
    else input='<textarea name="answer" required maxlength="4000" placeholder="À toi de jouer…"></textarea>';
    root.innerHTML='<p>'+esc(body)+'</p><form data-daily-answer data-daily-id="'+esc(id)+'">'+input+'<button class="button button-primary" type="submit">Répondre</button><small class="form-note"></small></form>';
    const range=root.querySelector('input[type="range"]');if(range)range.addEventListener('input',()=>root.querySelector('output').textContent=range.value);
  }

  async function load() {
    try {
      const [payload, participantsPayload] = await Promise.all([api('/api/account/dashboard'), api('/api/participants')]);
      const participantNames = Object.fromEntries(list(participantsPayload, 'participants').map(person => [String(person.id), pick(person, 'displayName', 'display_name', 'name')]));
      const participant = payload.participant || payload.user || {};
      const name = pick(participant, 'displayName', 'display_name', 'name') || 'toi';
      app.querySelector('[data-account-name]').textContent = name;
      app.querySelector('[data-account-avatar]').innerHTML = avatarMarkup(participant);
      const revelations = list(payload, 'revelations');
      const latest = payload.latestRevelation || payload.latest_revelation || revelations[0];
      app.querySelector('[data-latest-revelation]').innerHTML = revelationMarkup(latest, true);
      app.querySelector('[data-revelation-history]').innerHTML = revelations.length ? revelations.map(item => revelationMarkup(item)).join('') : '<div class="empty-state compact-empty"><strong>Personne n’a encore parlé.</strong><p>Enfin, officiellement.</p></div>';
      renderRankings(payload.rankingStats || payload.ranking_stats || payload.rankings || payload.averageRankings || payload.average_rankings || {});
      renderAnswers(list(payload, 'answers'), participantNames);
      renderReplies(payload.repliesReceived || payload.replies_received || []);
      if(payload.dailyQuestionEnabled) renderDaily(payload.dailyQuestion);
      const questionnaire = payload.questionnaire || {};
      const link = app.querySelector('[data-questionnaire-link]');
      const questionnaireUrl = pick(payload, 'questionnaireUrl', 'questionnaire_url') || pick(questionnaire, 'url', 'questionnaireUrl', 'questionnaire_url');
      const questionnaireComplete = pick(payload, 'questionnaireComplete', 'questionnaire_complete') ?? pick(questionnaire, 'completed', 'isComplete', 'is_complete');
      const remainingCount = Number(pick(questionnaire, 'remainingCount', 'remaining_count'));
      if (questionnaireUrl && questionnaireComplete !== true) {
        link.href = questionnaireUrl;
        link.textContent = Number.isFinite(remainingCount) ? `Continuer · ${remainingCount} question${remainingCount > 1 ? 's' : ''}` : 'Continuer le questionnaire';
        link.hidden = false;
      }
      app.querySelector('[data-account-loading]').hidden = true;
      app.querySelector('[data-account-content]').hidden = false;
    } catch (_) {
      app.querySelector('[data-account-loading]').hidden = true;
      app.querySelector('[data-account-error]').hidden = false;
    }
  }

  app.querySelector('[data-password-form]').addEventListener('submit', async event => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    const button = event.currentTarget.querySelector('button');
    const status = app.querySelector('[data-password-status]');
    const values = Object.fromEntries(new FormData(event.currentTarget));
    button.disabled = true; status.textContent = 'Mise à jour…';
    try { await api('/api/account/password', {method:'PATCH', body:JSON.stringify(values)}); event.currentTarget.reset(); status.textContent = 'Mot de passe changé.'; }
    catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
  const suggestionDialog=app.querySelector('[data-suggestion-dialog]'), suggestionForm=app.querySelector('[data-suggestion-form]');
  app.querySelector('[data-open-suggestion]').addEventListener('click',()=>suggestionDialog.showModal());
  suggestionForm.elements.type.addEventListener('change',event=>{const markers={free_text:'{person}',slider:'{person}',compare_two:'{person1} et {person2}',compare_three:'{person1}, {person2} et {person3}',choose_one:''};suggestionForm.querySelector('[data-suggestion-help]').textContent=markers[event.target.value]?'Utilise '+markers[event.target.value]+' dans ta question.':'Pas de placeholder : la personne choisie sera proposée dans la réponse.';});
  suggestionForm.addEventListener('submit',async event=>{event.preventDefault();if(!suggestionForm.reportValidity())return;const button=suggestionForm.querySelector('[type="submit"]'),status=suggestionForm.querySelector('[data-suggestion-status]'),data=new FormData(suggestionForm),markers={free_text:'{person}',slider:'{person}',compare_two:'{person1} et {person2}',compare_three:'{person1}, {person2} et {person3}',choose_one:''},required=markers[data.get('type')],body=String(data.get('body')||'');if(required&&required.split(' et ').some(marker=>!body.includes(marker))){status.textContent='Ajoute '+required+' dans ta question pour que les participants soient tirés automatiquement.';suggestionForm.elements.body.focus();return;}button.disabled=true;try{await api('/api/account/question-suggestions',{method:'POST',body:JSON.stringify(Object.fromEntries(data))});suggestionForm.reset();suggestionDialog.close();}catch(error){status.textContent=error.message;}finally{button.disabled=false;}});
  app.addEventListener('submit',async event=>{const form=event.target.closest('[data-daily-answer]');if(!form)return;event.preventDefault();if(!form.reportValidity())return;const button=form.querySelector('button'),status=form.querySelector('.form-note'),data=new FormData(form);let answer=data.get('answer');if(form.querySelector('.daily-choices'))answer={selectedParticipantId:answer,comment:data.get('comment')};button.disabled=true;status.textContent='Envoi…';try{await api('/api/account/daily-question/'+encodeURIComponent(form.dataset.dailyId)+'/answer',{method:'POST',body:JSON.stringify({answer})});form.innerHTML='<strong>Réponse enregistrée. À demain pour la suite.</strong>';}catch(error){status.textContent=error.message;button.disabled=false;}});

  load();
})();
