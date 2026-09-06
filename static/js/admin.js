(() => {
  const app = document.querySelector('[data-admin-app]');
  if (!app) return;

  const state = {participants: [], questions: [], answers: [], feedback: [], settings: {}, csrf: document.querySelector('meta[name="csrf-token"]')?.content || ''};
  const dialog = document.querySelector('[data-admin-dialog]');
  const entityForm = dialog.querySelector('[data-entity-form]');
  const status = app.querySelector('[data-admin-status]');
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const pick = (object, ...keys) => keys.map(key => object?.[key]).find(value => value !== undefined && value !== null);
  const unwrap = (payload, key) => Array.isArray(payload) ? payload : payload?.[key] || payload?.data?.[key] || payload?.data || [];
  const personName = person => pick(person, 'displayName', 'display_name', 'name') || 'Sans nom';

  async function api(path, options = {}) {
    const isFormData = options.body instanceof FormData;
    const headers = {'Accept': 'application/json', ...(options.body && !isFormData ? {'Content-Type': 'application/json'} : {}), ...options.headers};
    if (options.method && options.method !== 'GET') headers['X-CSRF-Token'] = state.csrf;
    const response = await fetch(path, {...options, headers});
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) { window.location.assign('/admin/login'); throw new Error('Session expirée.'); }
    if (!response.ok) throw new Error(payload.error || payload.message || 'L’opération a échoué.');
    return payload;
  }

  async function ensureCsrf() {
    if (state.csrf) return;
    try { const payload = await api('/api/admin/csrf'); state.csrf = payload.csrfToken || payload.csrf_token || ''; }
    catch (_) { /* The backend may rely on same-site cookies only. */ }
  }

  function announce(message, error = false) { status.textContent = message; status.style.color = error ? 'var(--coral-dark)' : ''; }

  function showTab(name) {
    app.querySelectorAll('[data-tab]').forEach(tab => tab.setAttribute('aria-selected', String(tab.dataset.tab === name)));
    app.querySelectorAll('[data-panel]').forEach(panel => panel.hidden = panel.dataset.panel !== name);
    history.replaceState(null, '', `#${name}`);
  }

  function bindTabs() {
    app.querySelectorAll('[data-tab]').forEach(tab => tab.addEventListener('click', () => showTab(tab.dataset.tab)));
    app.querySelectorAll('[data-goto]').forEach(button => button.addEventListener('click', () => showTab(button.dataset.goto)));
    const initial = location.hash.slice(1); if (app.querySelector(`[data-panel="${initial}"]`)) showTab(initial);
  }

  async function loadAll() {
    try {
      const [participantsPayload, questionsPayload, answersPayload, feedbackPayload, settingsPayload] = await Promise.all([
        api('/api/admin/participants'), api('/api/admin/questions'), api('/api/admin/answers'), api('/api/admin/feedback'), api('/api/admin/settings')
      ]);
      state.participants = unwrap(participantsPayload, 'participants');
      state.questions = unwrap(questionsPayload, 'questions');
      state.answers = unwrap(answersPayload, 'answers');
      state.feedback = unwrap(feedbackPayload, 'feedback');
      state.settings = settingsPayload.settings || settingsPayload.data || settingsPayload;
      renderAll(); announce('Tableau de bord à jour.');
    } catch (reason) { announce(reason.message, true); renderFailure(); }
  }

  function renderAll() { renderStats(); renderParticipants(); renderQuestions(); renderFilters(); renderAnswers(state.answers); renderFeedback(); renderLogoSettings(); }

  function renderStats() {
    const activeParticipants = state.participants.filter(item => pick(item, 'isActive', 'is_active') !== false).length;
    const activeQuestions = state.questions.filter(item => pick(item, 'isActive', 'is_active') !== false).length;
    const completed = new Set(state.answers.filter(answer => pick(answer, 'sessionCompleted', 'session_completed', 'completed')).map(answer => pick(answer, 'sessionId', 'session_id'))).size;
    const values = {participants:activeParticipants, questions:activeQuestions, completed, answers:state.answers.length};
    Object.entries(values).forEach(([key,value]) => { const node=app.querySelector(`[data-stat="${key}"]`); if(node) node.textContent=value; });
    const participation = app.querySelector('[data-participation-list]');
    if (!state.participants.length) { participation.innerHTML='<div class="empty-state"><strong>Personne sur la ligne de départ.</strong></div>'; return; }
    participation.innerHTML = state.participants.map(person => {
      const count=state.answers.filter(answer=>String(pick(answer,'authorParticipantId','author_participant_id'))===String(person.id)).length;
      const max=Math.max(1,state.questions.length), percent=Math.min(100,Math.round(count/max*100));
      return `<div class="participation-row"><strong>${esc(personName(person))}</strong><span class="mini-progress" aria-label="${percent}%"><span style="width:${percent}%"></span></span><span>${count} réponse${count>1?'s':''}</span></div>`;
    }).join('');
  }

  function renderParticipants(filter = '') {
    const tbody=app.querySelector('[data-participant-table]');
    const items=state.participants.filter(person=>personName(person).toLowerCase().includes(filter.toLowerCase()));
    if(!items.length){tbody.innerHTML='<tr><td colspan="4" class="loading-row">Aucun participant.</td></tr>';return;}
    tbody.innerHTML=items.map(person=>{const active=pick(person,'isActive','is_active')!==false;const avatar=pick(person,'profilePhotoUrl','profile_photo_url','choicePhotoUrl','choice_photo_url');const email=pick(person,'email')||'—';const phone=pick(person,'phone')||'—';return `<tr data-row-id="${esc(person.id)}"><td><span class="person-cell"><span class="mini-avatar">${avatar?`<img src="${esc(avatar)}" alt="">`:esc(personName(person).slice(0,2).toUpperCase())}</span>${esc(personName(person))}</span></td><td>${esc(email)}<br><small>${esc(phone)}</small></td><td><span class="badge ${active?'badge-active':'badge-inactive'}">${active?'Actif':'En pause'}</span></td><td><span class="table-actions"><button class="icon-button" type="button" data-edit-participant="${esc(person.id)}" aria-label="Modifier ${esc(personName(person))}">✎</button><button class="icon-button" type="button" data-toggle-participant="${esc(person.id)}" aria-label="${active?'Désactiver':'Activer'} ${esc(personName(person))}">${active?'Ⅱ':'▶'}</button></span></td></tr>`;}).join('');
  }

  function renderQuestions(filter = '') {
    const tbody=app.querySelector('[data-question-table]');
    const items=state.questions.filter(question=>(pick(question,'body','title')||'').toLowerCase().includes(filter.toLowerCase()));
    if(!items.length){tbody.innerHTML='<tr><td colspan="5" class="loading-row">Aucune question.</td></tr>';return;}
    tbody.innerHTML=items.map(question=>{const active=pick(question,'isActive','is_active')!==false;return `<tr><td>${esc(pick(question,'displayOrder','display_order')??0)}</td><td><strong>${esc(pick(question,'title')||'Sans titre')}</strong><br><small>${esc(pick(question,'body')||'')}</small></td><td><span class="badge badge-inactive">${esc(question.type)}</span><br><small>${esc(pick(question,'targetMode','target_mode')||'none')}</small></td><td><span class="badge ${active?'badge-active':'badge-inactive'}">${active?'Active':'En pause'}</span></td><td><span class="table-actions"><button class="icon-button" type="button" data-edit-question="${esc(question.id)}" aria-label="Modifier la question">✎</button><button class="icon-button" type="button" data-toggle-question="${esc(question.id)}" aria-label="${active?'Désactiver':'Activer'} la question">${active?'Ⅱ':'▶'}</button></span></td></tr>`;}).join('');
  }

  function renderFilters() {
    const form=app.querySelector('[data-answer-filters]');
    ['author_id','target_id'].forEach(name=>{const select=form.elements[name];const current=select.value;select.innerHTML=`<option value="">${name==='author_id'?'Tous':'Toutes'}</option>`+state.participants.map(person=>`<option value="${esc(person.id)}">${esc(personName(person))}</option>`).join('');select.value=current;});
    const select=form.elements.question_id,current=select.value;select.innerHTML='<option value="">Toutes</option>'+state.questions.map(question=>`<option value="${esc(question.id)}">${esc(question.title||question.body)}</option>`).join('');select.value=current;
  }

  function renderAnswers(items) {
    const list=app.querySelector('[data-answer-list]');
    if(!items.length){list.innerHTML='<div class="admin-card empty-state"><span aria-hidden="true">🔒</span><strong>Aucune réponse.</strong></div>';return;}
    list.innerHTML=items.map(answer=>{const author=pick(answer,'author','authorName','author_name')||personName(state.participants.find(person=>String(person.id)===String(pick(answer,'authorParticipantId','author_participant_id'))));const question=pick(answer,'renderedQuestion','renderedBody','rendered_body','questionBody','question_body','question')||'Question';const raw=pick(answer,'answer','answerText','answer_text','answerNumber','answer_number','answerJson','answer_json');const value=typeof raw==='object'?JSON.stringify(raw,null,2):raw;return `<article class="answer-card"><header><span>Par <strong>${esc(author)}</strong></span><time>${esc(pick(answer,'updatedAt','updated_at','createdAt','created_at')||'')}</time></header><h3>${esc(question)}</h3><blockquote>${esc(value??'—')}</blockquote></article>`;}).join('');
  }

  function renderFeedback() {
    const list=app.querySelector('[data-feedback-list]');
    if(!state.feedback.length){list.innerHTML='<div class="admin-card empty-state"><strong>Aucun message.</strong></div>';return;}
    list.innerHTML=state.feedback.map(item=>{const author=pick(item,'participant','participantName','participant_name')||'Anonyme';const date=pick(item,'updatedAt','updated_at','createdAt','created_at')||'';return `<article class="feedback-card"><header><strong>${esc(author)}</strong><time>${esc(date)}</time></header><p>${esc(item.message)}</p></article>`;}).join('');
  }

  function renderLogoSettings() {
    const preview=app.querySelector('[data-logo-preview]');
    const url=pick(state.settings,'logoUrl','logo_url');
    preview.innerHTML=url?`<img src="${esc(url)}" alt="Logo actuel">`:'<span aria-hidden="true">C</span>';
  }

  function renderFailure(){ app.querySelectorAll('.loading-row').forEach(node=>node.textContent='Chargement impossible. Recharge la page.'); }

  function openDialog(entity, item = null) {
    entityForm.reset(); entityForm.elements.entity.value=entity; entityForm.elements.id.value=item?.id||'';
    dialog.querySelector('[data-dialog-eyebrow]').textContent=item?'Modification':'Nouveau';dialog.querySelector('[data-dialog-title]').textContent=`${item?'Modifier':'Ajouter'} ${entity==='participant'?'un participant':'une question'}`;
    const participantFields=dialog.querySelector('[data-participant-fields]'), questionFields=dialog.querySelector('[data-question-fields]');
    participantFields.hidden=entity!=='participant';questionFields.hidden=entity!=='question';
    participantFields.querySelectorAll('input, select, textarea').forEach(field=>field.disabled=entity!=='participant');
    questionFields.querySelectorAll('input, select, textarea').forEach(field=>field.disabled=entity!=='question');
    if(item) Object.entries(item).forEach(([key,value])=>{const snake=key.replace(/[A-Z]/g,letter=>`_${letter.toLowerCase()}`);const field=entityForm.elements[key]||entityForm.elements[snake];if(!field)return;if(field.type==='checkbox')field.checked=Boolean(value);else field.value=value??'';});
    participantFields.querySelectorAll('[data-preview]').forEach(preview=>updateImagePreview(preview, entityForm.elements[preview.dataset.preview].value));
    dialog.showModal();
  }

  function formPayload() {
    const data=new FormData(entityForm), entity=data.get('entity');
    if(entity==='participant')return {displayName:data.get('display_name'),choicePhotoUrl:data.get('choice_photo_url')||null,profilePhotoUrl:data.get('profile_photo_url')||null,secretCode:data.get('secret_code')||null,isActive:data.get('is_active')==='on'};
    const payload={title:data.get('title'),body:data.get('body'),type:data.get('type'),targetMode:data.get('target_mode'),displayOrder:Number(data.get('display_order')),category:data.get('category'),allowSelfTarget:data.get('allow_self_target')==='on',isActive:data.get('is_active')==='on'};
    if(payload.type==='slider'){payload.scaleMin=Number(data.get('scale_min'));payload.scaleMax=Number(data.get('scale_max'));} return payload;
  }

  function updateImagePreview(preview, url) {
    preview.innerHTML=url?`<img src="${esc(url)}" alt="Aperçu">`:'<span class="upload-placeholder">Aucune image</span>';
  }

  function bindFileDrop(preview, input) {
    ['dragenter','dragover'].forEach(name=>preview.addEventListener(name,event=>{event.preventDefault();preview.classList.add('is-over');}));
    ['dragleave','drop'].forEach(name=>preview.addEventListener(name,event=>{event.preventDefault();preview.classList.remove('is-over');}));
    preview.addEventListener('drop',event=>{
      const files=event.dataTransfer.files;
      if(!files.length)return;
      input.files=files;
      updateImagePreview(preview,URL.createObjectURL(files[0]));
    });
  }

  async function uploadImage(file) {
    if (!file) throw new Error('Choisis une image.');
    const body=new FormData();body.append('image',file);
    const payload=await api('/api/admin/uploads',{method:'POST',body});
    return payload.url || payload.data?.url;
  }

  async function uploadParticipantImages() {
    for(const [fileName,urlName] of [['choice_photo_file','choice_photo_url'],['profile_photo_file','profile_photo_url']]) {
      const file=entityForm.elements[fileName].files[0];
      if(!file)continue;
      entityForm.elements[urlName].value=await uploadImage(file);
    }
  }

  async function saveEntity(event) {
    event.preventDefault();const entity=entityForm.elements.entity.value,id=entityForm.elements.id.value;const plural=entity==='participant'?'participants':'questions';const error=dialog.querySelector('[data-dialog-error]');error.hidden=true;
    try{if(entity==='participant')await uploadParticipantImages();await api(`/api/admin/${plural}${id?`/${encodeURIComponent(id)}`:''}`,{method:id?'PATCH':'POST',body:JSON.stringify(formPayload())});dialog.close();announce('Enregistré. Le peloton est à jour.');await loadAll();}
    catch(reason){error.textContent=reason.message;error.hidden=false;}
  }

  async function toggle(entity,id){const list=entity==='participant'?state.participants:state.questions;const item=list.find(candidate=>String(candidate.id)===String(id));const active=pick(item,'isActive','is_active')!==false;try{await api(`/api/admin/${entity==='participant'?'participants':'questions'}/${encodeURIComponent(id)}`,{method:'PATCH',body:JSON.stringify({isActive:!active})});await loadAll();}catch(reason){announce(reason.message,true);}}

  function bindActions() {
    app.querySelector('[data-open-create]').addEventListener('click',()=>openDialog(app.querySelector('[data-tab][aria-selected="true"]').dataset.tab==='questions'?'question':'participant'));
    app.addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;for(const entity of ['participant','question']){if(button.dataset[`edit${entity[0].toUpperCase()+entity.slice(1)}`]){const id=button.dataset[`edit${entity[0].toUpperCase()+entity.slice(1)}`];openDialog(entity,(entity==='participant'?state.participants:state.questions).find(item=>String(item.id)===String(id)));}if(button.dataset[`toggle${entity[0].toUpperCase()+entity.slice(1)}`])toggle(entity,button.dataset[`toggle${entity[0].toUpperCase()+entity.slice(1)}`]);}});
    app.querySelector('[data-search="participants"]').addEventListener('input',event=>renderParticipants(event.target.value));app.querySelector('[data-search="questions"]').addEventListener('input',event=>renderQuestions(event.target.value));
    app.querySelector('[data-answer-filters]').addEventListener('submit',event=>{event.preventDefault();const data=new FormData(event.target);renderAnswers(state.answers.filter(answer=>(!data.get('author_id')||String(pick(answer,'authorParticipantId','author_participant_id'))===data.get('author_id'))&&(!data.get('target_id')||String(pick(answer,'targetParticipantId','target_participant_id'))===data.get('target_id'))&&(!data.get('question_id')||String(pick(answer,'questionId','question_id'))===data.get('question_id'))));});
    app.querySelector('[data-generate]').addEventListener('click',async()=>{try{await api('/api/admin/questions/generate-instances',{method:'POST',body:'{}'});announce('Instances générées. Les questions sont sur la piste.');}catch(reason){announce(reason.message,true);}});
    entityForm.addEventListener('submit',saveEntity);entityForm.elements.type.addEventListener('change',event=>dialog.querySelector('[data-scale-fields]').hidden=event.target.value!=='slider');
    entityForm.querySelectorAll('input[type="file"]').forEach(input=>input.addEventListener('change',()=>{const file=input.files[0];const preview=entityForm.querySelector(`[data-preview="${input.name.replace('_file','_url')}"]`);if(file&&preview)updateImagePreview(preview,URL.createObjectURL(file));}));
    entityForm.querySelectorAll('[data-preview]').forEach(preview=>bindFileDrop(preview,entityForm.elements[preview.dataset.preview.replace('_url','_file')]));
    const logoForm=app.querySelector('[data-logo-form]');
    bindFileDrop(app.querySelector('[data-logo-preview]'),logoForm.elements.image);
    logoForm.elements.image.addEventListener('change',()=>{const file=logoForm.elements.image.files[0];if(file)updateImagePreview(app.querySelector('[data-logo-preview]'),URL.createObjectURL(file));});
    logoForm.addEventListener('submit',async event=>{event.preventDefault();const button=logoForm.querySelector('button[type="submit"]');button.disabled=true;try{const logoUrl=await uploadImage(logoForm.elements.image.files[0]);await api('/api/admin/settings',{method:'PATCH',body:JSON.stringify({logoUrl})});state.settings.logoUrl=logoUrl;renderLogoSettings();logoForm.reset();announce('Logo mis à jour.');}catch(reason){announce(reason.message,true);}finally{button.disabled=false;}});
  }

  bindTabs();bindActions();ensureCsrf().then(loadAll);
})();
