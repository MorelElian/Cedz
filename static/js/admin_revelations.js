(() => {
  const app = document.querySelector('[data-admin-app]');
  if (!app) return;

  const state = {review: [], sent: [], phrases: [], refreshId: null, currentMail: null};
  const siteLogoUrl = app.dataset.siteLogoUrl || '';
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const pick = (object, ...keys) => keys.map(key => object?.[key]).find(value => value !== undefined && value !== null);
  const unwrap = (payload, key) => Array.isArray(payload) ? payload : payload?.[key] || payload?.data?.[key] || payload?.data || [];
  const person = (item, prefix) => item?.[prefix] || item?.[`${prefix}Participant`] || item?.[`${prefix}_participant`] || {};
  const personName = value => pick(value, 'displayName', 'display_name', 'name') || 'Inconnu';

  async function api(path, options = {}) {
    const isForm = options.body instanceof FormData;
    const headers = {'Accept':'application/json', ...(options.body && !isForm ? {'Content-Type':'application/json'} : {}), ...options.headers};
    if (options.method && options.method !== 'GET' && csrf) headers['X-CSRF-Token'] = csrf;
    const response = await fetch(path, {...options, headers});
    if (response.status === 401) { window.location.assign('/admin/login'); throw new Error('Session admin expirée.'); }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || payload.message || 'L’opération a échoué.');
    return payload.data || payload;
  }

  const typeMeta = rawType => {
    const type = String(rawType || 'free_text').toLowerCase();
    if (type.includes('ranking')) return {label:'Classement', className:'ranking', mark:'1.'};
    if (type.includes('split') || type.includes('binary')) return {label:'Deux camps', className:'split', mark:'↔'};
    if (type.includes('three') || type.includes('trio')) return {label:'Trio', className:'duel', mark:'×3'};
    if (type.includes('compare') || type.includes('duel')) return {label:'Duel', className:'duel', mark:'VS'};
    if (type.includes('slider') || type.includes('number')) return {label:'Estimation', className:'number', mark:'#'};
    return {label:'Réponse libre', className:'text', mark:'“'};
  };

  function avatar(value, label) {
    const url = pick(value, 'profilePhotoUrl', 'profile_photo_url', 'avatarUrl', 'avatar_url');
    return url ? `<img src="${esc(url)}" alt="">` : `<span>${esc(label.slice(0, 2).toUpperCase())}</span>`;
  }

  function copyMarkup(value) {
    const separated = String(value ?? '').replace(/([.!?])\s+(?=[A-ZÀ-Ö])/g, '$1\n\n');
    const paragraphs = separated.split(/(?:\r?\n){2,}/).map(part => part.trim()).filter(Boolean);
    return `<div class="mail-copy">${paragraphs.map(part => `<p>${esc(part)}</p>`).join('')}</div>`;
  }

  function previewMarkup(item, compact = false) {
    const author = person(item, 'author'), recipient = person(item, 'recipient');
    const authorName = pick(item, 'authorName', 'author_name') || personName(author);
    const recipientName = pick(item, 'recipientName', 'recipient_name') || personName(recipient);
    const intro = pick(item, 'intro', 'introText', 'intro_text') || 'Le comité a parlé.';
    const question = pick(item, 'question', 'questionText', 'question_text') || '';
    const content = pick(item, 'finalContent', 'final_content', 'content', 'body') || '—';
    const type = typeMeta(pick(item, 'type', 'revelationType', 'revelation_type', 'answerType', 'answer_type'));
    return `<div class="mail-preview mail-type-${type.className}${compact ? ' is-compact' : ''}">
      <div class="mail-preview-top"><span class="mail-logo">${siteLogoUrl ? `<img src="${esc(siteLogoUrl)}" alt="Cedz">` : 'CEDZ'}</span><span>T24 · DOSSIER CONFIDENTIEL</span></div>
      <div class="mail-preview-person"><span class="author-face">${avatar(author, authorName)}</span><span><small>${esc(type.label)} pour ${esc(recipientName)}</small><strong>${esc(authorName)} a parlé.</strong></span><b aria-hidden="true">${type.mark}</b></div>
      <p class="mail-intro">${esc(intro)}</p>
      ${question ? `<p class="mail-question">${esc(question)}</p>` : ''}
      ${copyMarkup(content)}
      <span class="mail-fake-link">Voir le détail et répondre →</span>
    </div>`;
  }

  function renderReview() {
    const grid = app.querySelector('[data-revelation-review-grid]');
    const summary = app.querySelector('[data-review-summary]');
    summary.textContent = `${state.review.length}/10 destinataires ont une proposition.`;
    if (!state.review.length) { grid.innerHTML = '<div class="admin-card empty-state"><strong>Aucune proposition disponible.</strong><p>Importe des réponses ou recharge le tirage.</p></div>'; return; }
    grid.innerHTML = state.review.map(item => {
      const recipient = person(item, 'recipient'), author = person(item, 'author');
      const recipientName = pick(item, 'recipientName', 'recipient_name') || personName(recipient);
      const authorName = pick(item, 'authorName', 'author_name') || personName(author);
      const email = pick(item, 'recipientEmail', 'recipient_email') || pick(recipient, 'email') || '';
      const type = typeMeta(pick(item, 'type', 'revelationType', 'revelation_type'));
      const id = pick(item, 'id', 'revelationId', 'revelation_id');
      return `<article class="review-card" data-review-id="${esc(id)}">
        <header><span class="mini-avatar">${avatar(recipient, recipientName)}</span><span><strong>${esc(recipientName)}</strong><small>${email ? esc(email) : 'Email manquant'}</small></span><span class="badge badge-${type.className}">${esc(type.label)}</span></header>
        ${previewMarkup(item, true)}
        <dl class="mail-routing"><div><dt>Auteur</dt><dd>${esc(authorName)}</dd></div><div><dt>Destinataire</dt><dd>${esc(recipientName)}</dd></div></dl>
        ${!email ? '<p class="blocking-note" role="alert">Ajoute son email dans Participants avant l’envoi.</p>' : ''}
        <footer><button class="button button-ghost button-small" type="button" data-refresh-revelation="${esc(id)}">Changer</button><button class="button button-secondary button-small" type="button" data-edit-revelation="${esc(id)}">Aperçu / modifier</button><button class="button button-primary button-small" type="button" data-send-revelation="${esc(id)}" ${email ? '' : 'disabled'}>Accepter et envoyer</button></footer>
      </article>`;
    }).join('');
  }

  function renderSent() {
    const root = app.querySelector('[data-sent-history]');
    if (!state.sent.length) { root.innerHTML = '<div class="admin-card empty-state"><strong>Rien n’est encore parti.</strong></div>'; return; }
    root.innerHTML = state.sent.map(item => {
      const recipient = person(item, 'recipient'), author = person(item, 'author');
      const recipientName = pick(item, 'recipientName', 'recipient_name') || personName(recipient);
      const authorName = pick(item, 'authorName', 'author_name') || personName(author);
      const sentAt = pick(item, 'sentAt', 'sent_at') || '';
      return `<article class="sent-card"><span class="mini-avatar">${avatar(recipient, recipientName)}</span><div><strong>${esc(recipientName)}</strong><p>Par ${esc(authorName)} · ${esc(pick(item, 'subject', 'title') || 'Révélation')}</p></div><time>${esc(sentAt ? new Date(sentAt).toLocaleString('fr-FR') : 'Envoyé')}</time><button class="text-button" type="button" data-view-sent="${esc(pick(item, 'id'))}">Voir la copie</button></article>`;
    }).join('');
  }

  function renderPhrases() {
    const root = app.querySelector('[data-intro-phrases]');
    const tones = [['pique','Pique'],['positif','Positif']];
    root.innerHTML = tones.map(([tone, label]) => {
      const items = state.phrases.filter(item => pick(item, 'isActive', 'is_active') !== false).filter(item => {
        const itemTone = pick(item, 'tone') || 'pique';
        return (itemTone === 'positive' ? 'positif' : itemTone) === tone;
      });
      return `<section class="phrase-column"><header><h3>${label}</h3><span>${items.length}</span></header><div>${items.length ? items.map(item => `<article class="phrase-card"><p>${esc(pick(item, 'text', 'content'))}</p><footer><button class="icon-button" type="button" data-edit-intro="${esc(item.id)}" aria-label="Modifier">✎</button><button class="icon-button is-danger" type="button" data-delete-intro="${esc(item.id)}" aria-label="Supprimer">×</button></footer></article>`).join('') : '<p class="empty-copy">Aucune phrase.</p>'}</div></section>`;
    }).join('');
  }

  function renderAdminReplies(items) {
    const root = app.querySelector('[data-admin-replies]');
    if (!items.length) { root.innerHTML = '<div class="admin-card empty-state"><strong>Aucune réponse reçue.</strong></div>'; return; }
    root.innerHTML = items.map(item => `<article class="received-reply"><header><strong>${esc(pick(item,'fromParticipant','from_participant','participantName','participant_name') || 'Participant')}</strong><small>à ${esc(pick(item,'authorName','author_name','toParticipant','to_participant') || 'l’auteur')}</small><time>${esc(pick(item,'createdAt','created_at') || '')}</time></header><blockquote>${esc(pick(item,'message','content') || '—')}</blockquote></article>`).join('');
  }

  async function loadReview() {
    const root = app.querySelector('[data-revelation-review-grid]'); root.setAttribute('aria-busy','true');
    try { state.review = unwrap(await api('/api/admin/revelations/review'), 'revelations'); renderReview(); }
    catch (error) { root.innerHTML = `<div class="admin-card error-state"><strong>Impossible de préparer les mails.</strong><p>${esc(error.message)}</p></div>`; }
    finally { root.setAttribute('aria-busy','false'); }
  }

  async function loadSent() {
    try {
      state.sent = unwrap(await api('/api/admin/revelations/sent'), 'revelations'); renderSent();
      let replies = state.sent.flatMap(item => item.replies || (item.reply ? [item.reply] : []));
      if (!replies.length) {
        try { replies = unwrap(await api('/api/admin/revelation-replies'), 'replies'); } catch (_) { replies = []; }
      }
      renderAdminReplies(replies);
    }
    catch (error) { app.querySelector('[data-sent-history]').innerHTML = `<div class="admin-card error-state"><strong>Historique indisponible.</strong><p>${esc(error.message)}</p></div>`; }
  }

  async function loadPhrases() {
    try { state.phrases = unwrap(await api('/api/admin/intro-phrases'), 'phrases'); renderPhrases(); }
    catch (error) { app.querySelector('[data-intro-phrases]').innerHTML = `<div class="admin-card error-state"><strong>Phrases indisponibles.</strong><p>${esc(error.message)}</p></div>`; }
  }

  const mailDialog = document.querySelector('[data-mail-dialog]');
  const mailForm = mailDialog.querySelector('[data-mail-edit-form]');
  function openMail(item) {
    state.currentMail = item;
    const id = pick(item, 'id', 'revelationId', 'revelation_id');
    const recipient = person(item, 'recipient');
    mailForm.elements.id.value = id;
    mailForm.elements.intro.value = pick(item, 'intro', 'introText', 'intro_text') || '';
    mailForm.elements.finalContent.value = pick(item, 'finalContent', 'final_content', 'content', 'body') || '';
    mailDialog.querySelector('[data-mail-dialog-title]').textContent = `Pour ${pick(item, 'recipientName', 'recipient_name') || personName(recipient)}`;
    const isSent = pick(item, 'status') === 'sent';
    const preview = mailDialog.querySelector('[data-mail-full-preview]');
    const htmlSnapshot = pick(item, 'htmlSnapshot', 'html_snapshot');
    preview.innerHTML = '';
    if (isSent && htmlSnapshot) {
      const frame = document.createElement('iframe');
      frame.title = 'Copie exacte du mail envoyé'; frame.setAttribute('sandbox', ''); frame.srcdoc = htmlSnapshot;
      preview.append(frame);
    } else preview.innerHTML = previewMarkup(item);
    mailForm.elements.intro.disabled = isSent;
    mailForm.elements.finalContent.disabled = isSent;
    mailForm.querySelector('button[type="submit"]').hidden = isSent;
    mailDialog.querySelector('[data-send-from-dialog]').hidden = isSent;
    mailDialog.showModal();
  }
  function previewEdited() {
    if (!state.currentMail) return;
    const edited = {...state.currentMail, intro:mailForm.elements.intro.value, finalContent:mailForm.elements.finalContent.value};
    mailDialog.querySelector('[data-mail-full-preview]').innerHTML = previewMarkup(edited);
  }

  async function saveMail() {
    const id = mailForm.elements.id.value;
    return api(`/api/admin/revelations/${encodeURIComponent(id)}`, {method:'PATCH', body:JSON.stringify({intro:mailForm.elements.intro.value.trim(), finalContent:mailForm.elements.finalContent.value.trim()})});
  }
  async function sendMail(id) {
    const item = state.review.find(candidate => String(pick(candidate,'id','revelationId','revelation_id')) === String(id));
    const recipient = person(item, 'recipient');
    if (!(pick(item, 'recipientEmail', 'recipient_email') || pick(recipient, 'email'))) throw new Error('Email destinataire manquant.');
    await api(`/api/admin/revelations/${encodeURIComponent(id)}/send`, {method:'POST', body:'{}'});
    await Promise.all([loadReview(), loadSent()]);
  }

  const refreshDialog = document.querySelector('[data-refresh-dialog]');
  const introDialog = document.querySelector('[data-intro-dialog]');
  const introForm = introDialog.querySelector('[data-intro-form]');
  const passwordDialog = document.querySelector('[data-password-dialog]');

  app.addEventListener('click', async event => {
    const button = event.target.closest('button'); if (!button) return;
    if (button.dataset.editRevelation) openMail(state.review.find(item => String(pick(item,'id','revelationId','revelation_id')) === button.dataset.editRevelation));
    if (button.dataset.viewSent) openMail(state.sent.find(item => String(item.id) === button.dataset.viewSent));
    if (button.dataset.refreshRevelation) { state.refreshId = button.dataset.refreshRevelation; refreshDialog.showModal(); }
    if (button.dataset.sendRevelation) {
      button.disabled = true;
      try { await sendMail(button.dataset.sendRevelation); }
      catch (error) { button.disabled = false; window.alert(error.message); }
    }
    if (button.matches('[data-reload-revelations]')) loadReview();
    if (button.matches('[data-add-intro]')) { introForm.reset(); introForm.elements.id.value=''; introDialog.querySelector('[data-intro-dialog-title]').textContent='Ajouter'; introDialog.showModal(); }
    if (button.dataset.editIntro) {
      const item=state.phrases.find(phrase=>String(phrase.id)===button.dataset.editIntro); introForm.elements.id.value=item.id; introForm.elements.text.value=pick(item,'text','content'); introForm.elements.tone.value=item.tone==='positive'?'positif':item.tone; introDialog.querySelector('[data-intro-dialog-title]').textContent='Modifier'; introDialog.showModal();
    }
    if (button.dataset.deleteIntro && window.confirm('Supprimer cette phrase ?')) { try { await api(`/api/admin/intro-phrases/${encodeURIComponent(button.dataset.deleteIntro)}`,{method:'DELETE'}); await loadPhrases(); } catch(error){window.alert(error.message);} }
    if (button.dataset.setPassword) {
      const form=passwordDialog.querySelector('[data-admin-password-form]'); form.reset(); form.elements.participantId.value=button.dataset.setPassword; passwordDialog.querySelector('[data-password-title]').textContent=`Mot de passe · ${button.dataset.personName}`; passwordDialog.showModal();
    }
  });

  refreshDialog.addEventListener('click', async event => {
    const button=event.target.closest('[data-refresh-action]'); if(!button)return; button.disabled=true;
    try { await api(`/api/admin/revelations/${encodeURIComponent(state.refreshId)}/refresh`,{method:'POST',body:JSON.stringify({action:button.dataset.refreshAction})}); refreshDialog.close(); await loadReview(); }
    catch(error){window.alert(error.message);} finally{button.disabled=false;}
  });
  mailForm.addEventListener('input', previewEdited);
  mailForm.addEventListener('submit', async event => { event.preventDefault(); if(!event.currentTarget.reportValidity())return; try{await saveMail();mailDialog.close();await loadReview();}catch(error){const node=mailDialog.querySelector('[data-mail-error]');node.textContent=error.message;node.hidden=false;} });
  mailDialog.querySelector('[data-send-from-dialog]').addEventListener('click',async event=>{if(!mailForm.reportValidity())return;event.currentTarget.disabled=true;try{await saveMail();await sendMail(mailForm.elements.id.value);mailDialog.close();}catch(error){const node=mailDialog.querySelector('[data-mail-error]');node.textContent=error.message;node.hidden=false;}finally{event.currentTarget.disabled=false;}});
  introForm.addEventListener('submit',async event=>{event.preventDefault();if(!event.currentTarget.reportValidity())return;const id=introForm.elements.id.value;try{await api(`/api/admin/intro-phrases${id?'/'+encodeURIComponent(id):''}`,{method:id?'PATCH':'POST',body:JSON.stringify({text:introForm.elements.text.value.trim(),tone:introForm.elements.tone.value})});introDialog.close();await loadPhrases();}catch(error){window.alert(error.message);}});
  passwordDialog.querySelector('[data-admin-password-form]').addEventListener('submit',async event=>{event.preventDefault();if(!event.currentTarget.reportValidity())return;const status=passwordDialog.querySelector('[data-admin-password-status]');const id=event.currentTarget.elements.participantId.value;try{await api(`/api/admin/participants/${encodeURIComponent(id)}/password`,{method:'PATCH',body:JSON.stringify({password:event.currentTarget.elements.password.value})});status.textContent='Mot de passe défini.';event.currentTarget.elements.password.value='';}catch(error){status.textContent=error.message;}});
  app.querySelector('[data-answer-import]').addEventListener('submit',async event=>{event.preventDefault();const file=event.currentTarget.elements.file.files[0];if(!file)return;const body=new FormData();body.append('file',file);const status=event.currentTarget.querySelector('[data-import-status]');status.textContent='Import…';try{const result=await api('/api/admin/import-answers',{method:'POST',body});status.textContent=`${pick(result,'importedCount','imported_count') ?? 'Import'} terminé.`;event.currentTarget.reset();}catch(error){status.textContent=error.message;}});

  Promise.all([loadReview(), loadSent(), loadPhrases()]);
})();
