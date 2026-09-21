(() => {
  const app = document.querySelector('[data-questionnaire]');
  if (!app) return;

  const sessionId = app.dataset.sessionId;
  const reviewMode = app.dataset.reviewMode === 'true';
  const stage = app.querySelector('[data-question-stage]');
  const nav = app.querySelector('[data-question-nav]');
  const previous = app.querySelector('[data-previous]');
  const next = app.querySelector('[data-next]');
  const currentLabel = app.querySelector('[data-progress-current]');
  const totalLabel = app.querySelector('[data-progress-total]');
  const progress = app.querySelector('[data-progress-track]');
  const progressBar = app.querySelector('[data-progress-bar]');
  const saveStatus = document.querySelector('[data-save-status]');
  const template = document.querySelector('#question-template');
  const errorTemplate = document.querySelector('#error-template');
  const quote = document.querySelector('[data-question-quote]');
  const quoteSource = document.querySelector('[data-question-quote-source]');
  const reviewList = app.querySelector('[data-review-question-list]');
  const reviewSelect = app.querySelector('[data-review-question-select]');
  const quotes = [
    {text: 'Il faut avoir de la persévérance, et surtout de la confiance en soi.', author: 'Marie Curie', url: 'https://fr.wikiquote.org/wiki/Marie_Curie'},
    {text: "Le génie n'est qu'une plus grande aptitude à la patience.", author: 'Buffon', url: 'https://fr.wikiquote.org/wiki/Patience'},
    {text: "Il n'y a point de chemin trop long à qui marche lentement et sans se presser.", author: 'La Bruyère', url: 'https://fr.wikiquote.org/wiki/Patience'},
    {text: "Résistance n'est qu'espérance.", author: 'René Char', url: 'https://fr.wikiquote.org/wiki/Esp%C3%A9rance'},
    {text: "Le courage est comme un brasier endormi. Il suffit d'un peu de souffle pour qu'il s'enflamme !", author: 'Alexandre Najjar', url: 'https://fr.wikiquote.org/wiki/Courage'},
    {text: 'Patience et longueur de temps font plus que force ni que rage.', author: 'Jean de La Fontaine', url: 'https://fr.wikiquote.org/wiki/Jean_de_La_Fontaine'},
    {text: 'Qui veut voyager loin, ménage sa monture.', author: 'Jean Racine', url: 'https://fr.wikiquote.org/wiki/Jean_Racine'},
    {text: "J'ai appris que le courage n'est pas l'absence de peur mais la capacité à la vaincre.", author: 'Nelson Mandela', url: 'https://fr.wikiquote.org/wiki/Nelson_Mandela'},
  ];
  let questions = [], participants = [], index = 0, answers = new Map(), saveTimer;

  const unwrap = (payload, key) => Array.isArray(payload) ? payload : payload?.[key] || payload?.data?.[key] || payload?.data || [];
  const idOf = item => item?.id ?? item?.participant_id ?? item?.question_instance_id;
  const nameOf = item => item?.displayName ?? item?.display_name ?? item?.name ?? item?.label ?? String(item ?? '');
  const candidatesOf = question => {
    const explicit = question.options || question.participants || question.targets || question.target_participants;
    if (explicit?.length) return explicit;
    if (question.type === 'ranking' || question.type === 'binary_split' || question.type === 'choose_one') return participants;
    const targetIds = (question.targetParticipantIds || []).map(String);
    return participants.filter(person => targetIds.includes(String(idOf(person))));
  };
  const questionId = question => question.questionInstanceId || question.instanceId || question.question_instance_id || question.instance_id || question.id;
  const typeLabels = {free_text: 'Réponse libre', single_person_answer: 'Portrait-robot', choose_one: 'Choisis quelqu’un', compare_two: 'Duel', compare_three: 'Match à trois', ranking: 'Classement', binary_split: 'Deux camps', slider: 'Curseur'};

  async function load() {
    stage.setAttribute('aria-busy', 'true');
    try {
      const reviewQuery = reviewMode ? '?review=1' : '';
      const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/questions${reviewQuery}`, {headers: {'Accept':'application/json'}});
      if (!response.ok) throw new Error();
      const payload = await response.json();
      questions = unwrap(payload, 'questions');
      participants = payload.participants || payload.data?.participants || [];
      const existing = payload.answersByInstance || payload.answers_by_instance || payload.answers || payload.data?.answers || {};
      if (Array.isArray(existing)) existing.forEach(answer => answers.set(String(answer.question_instance_id || answer.question_id || answer.questionInstanceId), answer.answer_json ?? answer.answer_number ?? answer.answer_text ?? answer.value ?? answer.answer));
      else Object.entries(existing).forEach(([instanceId, answer]) => answers.set(String(instanceId), answer));
      index = Math.max(0, Number(payload.current_index || payload.data?.current_index || 0));
      totalLabel.textContent = questions.length;
      if (reviewMode) {
        reviewList.hidden = false;
        previous.hidden = true;
        nav.querySelector('.keyboard-hint')?.setAttribute('hidden', '');
        renderReviewList();
      }
      if (!questions.length && Number(payload.remainingCount ?? payload.remaining_count) === 0) return complete();
      if (!questions.length) return showEmpty();
      nav.hidden = false;
      render();
    } catch (_) { showError(); }
    finally { stage.setAttribute('aria-busy', 'false'); }
  }

  function showEmpty() {
    stage.innerHTML = '<div class="empty-state"><span aria-hidden="true">🏁</span><h2>Aucune question.</h2><p>Reviens un peu plus tard.</p></div>';
  }

  function showError() {
    stage.replaceChildren(errorTemplate.content.cloneNode(true));
    stage.querySelector('[data-retry]').addEventListener('click', load);
  }

  function render() {
    const question = questions[index];
    const fragment = template.content.cloneNode(true);
    const form = fragment.querySelector('form');
    form.dataset.questionId = questionId(question);
    form.querySelector('.question-type').textContent = typeLabels[question.type] || question.type || 'Question';
    form.querySelector('.question-target').textContent = question.category || 'T24';
    form.querySelector('.question-body').textContent = question.rendered_body || question.body || question.question || question.title;
    form.querySelector('.question-help').textContent = helpFor(question.type);
    form.querySelector('.answer-zone').append(buildAnswer(question));
    form.addEventListener('input', queueSave);
    form.addEventListener('change', queueSave);
    stage.replaceChildren(fragment);
    const percent = ((index + 1) / questions.length) * 100;
    currentLabel.textContent = index + 1;
    progress.setAttribute('aria-valuenow', Math.round(percent));
    progressBar.style.width = `${percent}%`;
    renderQuote(index);
    previous.disabled = index === 0;
    next.disabled = false;
    next.innerHTML = reviewMode
      ? 'Enregistrer <span aria-hidden="true">✓</span>'
      : (index === questions.length - 1 ? 'Terminer <span aria-hidden="true">✓</span>' : 'Suivante <span aria-hidden="true">→</span>');
    if (reviewMode) renderReviewList();
    stage.querySelector('textarea, input, button:not([draggable="true"])')?.focus({preventScroll: true});
  }

  function renderReviewList() {
    if (!reviewMode || !reviewSelect) return;
    reviewSelect.replaceChildren(...questions.map((question, questionIndex) => {
      const body = question.rendered_body || question.body || question.question || question.title || 'Question';
      const option = document.createElement('option');
      option.value = String(questionIndex);
      option.textContent = `${questionIndex + 1}. ${body}`;
      option.selected = questionIndex === index;
      return option;
    }));
  }

  function renderQuote(questionIndex) {
    if (!quote || !quoteSource) return;
    const item = quotes[questionIndex % quotes.length];
    quote.textContent = item.text;
    quoteSource.textContent = item.author;
    quoteSource.href = item.url;
  }

  function helpFor(type) {
    return ({ranking:'Remets le groupe dans l’ordre, puis donne ton temps par tour.', binary_split:'Choisis un camp pour chaque personne.', slider:'Place le curseur.', compare_two:'Choisis ton favori.', compare_three:'Un seul choix.'})[type] || 'Fais au plus honnête.';
  }

  function buildAnswer(question) {
    const type = question.type || 'free_text';
    const saved = answers.get(String(questionId(question)));
    if (type === 'slider') return buildSlider(question, saved);
    if (type === 'ranking') return buildRanking(question, saved);
    if (type === 'binary_split') return buildSplit(question, saved);
    if (type === 'compare_two' || type === 'compare_three' || type === 'choose_one') return buildChoice(question, saved, true);
    const textarea = document.createElement('textarea');
    textarea.name = 'answer_text'; textarea.placeholder = 'Ta réponse…'; textarea.maxLength = 2000;
    textarea.value = typeof saved === 'string' ? saved : saved?.answer_text || '';
    return textarea;
  }

  function buildChoice(question, saved, comment) {
    const wrapper = document.createElement('div');
    const choices = document.createElement('div'); choices.className = 'choice-grid';
    const selected = saved?.selected_participant_id || saved?.selectedParticipantId || saved;
    candidatesOf(question).forEach(person => {
      const label = document.createElement('label'); label.className = 'choice-card';
      const input = document.createElement('input'); input.type = 'radio'; input.name = 'selected_participant_id'; input.value = idOf(person); input.required = true; input.checked = String(selected) === String(idOf(person));
      label.append(input, document.createTextNode(nameOf(person))); choices.append(label);
    });
    wrapper.append(choices);
    if (comment) {
      const field = document.createElement('label'); field.className = 'field comment-field'; field.innerHTML = '<span>Un commentaire ? <small>(facultatif)</small></span>';
      const textarea = document.createElement('textarea'); textarea.name = 'comment'; textarea.rows = 3; textarea.placeholder = 'Balance…'; textarea.value = saved?.comment || '';
      field.append(textarea); wrapper.append(field);
    }
    return wrapper;
  }

  function buildSlider(question, saved) {
    const min = Number(question.scale_min ?? question.scaleMin ?? 0), max = Number(question.scale_max ?? question.scaleMax ?? 100), value = Number(saved?.answer_number ?? saved ?? Math.round((min + max) / 2));
    const wrapper = document.createElement('div'); wrapper.className = 'range-wrap';
    const output = document.createElement('output'); output.className = 'range-value'; output.textContent = value;
    const input = document.createElement('input'); input.type = 'range'; input.name = 'answer_number'; input.min = min; input.max = max; input.value = value; input.setAttribute('aria-label', `Note entre ${min} et ${max}`); input.addEventListener('input', () => output.textContent = input.value);
    const labels = document.createElement('div'); labels.className = 'range-labels'; labels.innerHTML = `<span>${min}</span><span>${max}</span>`;
    wrapper.append(output, input, labels); return wrapper;
  }

  function buildRanking(question, saved) {
    const wrapper = document.createElement('div'); wrapper.className = 'ranking-answer';
    const people = [...candidatesOf(question)];
    const ordered = (saved?.ordered_participant_ids || saved?.orderedParticipantIds || []).map(String);
    if (ordered.length) people.sort((a,b) => ordered.indexOf(String(idOf(a))) - ordered.indexOf(String(idOf(b))));
    const list = document.createElement('ol'); list.className = 'ranking-list';
    people.forEach(person => {
      const item = document.createElement('li'); item.className = 'ranking-item'; item.dataset.id = idOf(person); item.draggable = true;
      const grip = document.createElement('span'); grip.className = 'drag-grip'; grip.setAttribute('aria-hidden', 'true'); grip.textContent = '⋮⋮';
      const name = document.createElement('strong'); name.textContent = nameOf(person);
      const actions = document.createElement('span'); actions.className = 'rank-actions';
      [['↑','Monter',-1],['↓','Descendre',1]].forEach(([symbol,label,direction]) => { const button=document.createElement('button'); button.type='button'; button.textContent=symbol; button.setAttribute('aria-label',`${label} ${nameOf(person)}`); button.addEventListener('click',()=>moveRank(item,direction)); actions.append(button); });
      item.append(grip, name, actions); list.append(item);
    });
    bindRankingDrag(list);
    const field = document.createElement('label'); field.className = 'field lap-time-field';
    const label = document.createElement('span'); label.textContent = 'Temps par tour';
    const input = document.createElement('input');
    input.type = 'text'; input.name = 'lap_time'; input.required = true; input.maxLength = 100;
    input.placeholder = 'Ex. 12 min 30'; input.autocomplete = 'off';
    input.value = saved?.lap_time || saved?.lapTime || '';
    field.append(label, input);
    wrapper.append(list, field);
    return wrapper;
  }

  function bindRankingDrag(list) {
    let dragged = null;
    list.addEventListener('dragstart', event => {
      dragged = event.target.closest('.ranking-item');
      if (!dragged) return;
      dragged.classList.add('is-dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', dragged.dataset.id);
    });
    list.addEventListener('dragover', event => {
      event.preventDefault();
      if (!dragged) return;
      const hovered = event.target.closest('.ranking-item');
      if (!hovered || hovered === dragged) return;
      const before = event.clientY < hovered.getBoundingClientRect().top + hovered.offsetHeight / 2;
      list.insertBefore(dragged, before ? hovered : hovered.nextSibling);
    });
    list.addEventListener('drop', event => { event.preventDefault(); queueSave(); });
    list.addEventListener('dragend', () => {
      dragged?.classList.remove('is-dragging');
      dragged = null;
    });
  }

  function moveRank(item, direction) {
    const sibling = direction < 0 ? item.previousElementSibling : item.nextElementSibling;
    if (!sibling) return;
    direction < 0 ? item.parentNode.insertBefore(item, sibling) : item.parentNode.insertBefore(sibling, item);
    queueSave(); item.querySelector('button')?.focus();
  }

  function buildSplit(question, saved) {
    const labels = question.categoryLabels || ['Camp A', 'Camp B'];
    const a = new Set((saved?.category_a || []).map(String)), b = new Set((saved?.category_b || []).map(String));
    const board = document.createElement('div'); board.className = 'split-board';
    const zones = [
      makeSplitZone('À placer', 'pool', 'split-pool'),
      makeSplitZone(labels[0], 'a'),
      makeSplitZone(labels[1], 'b'),
    ];
    zones.forEach(zone => board.append(zone));
    const containers = Object.fromEntries(zones.map(zone => [zone.dataset.category, zone.querySelector('.split-options')]));
    candidatesOf(question).forEach(person => {
      const id = String(idOf(person));
      const card = document.createElement('button');
      card.type = 'button'; card.className = 'split-person'; card.dataset.id = id; card.draggable = true;
      const grip = document.createElement('span'); grip.className = 'drag-grip'; grip.setAttribute('aria-hidden', 'true'); grip.textContent = '⋮⋮';
      const name = document.createElement('strong'); name.textContent = nameOf(person);
      card.append(grip, name);
      card.setAttribute('aria-label', `${nameOf(person)}, déplacer dans un groupe`);
      containers[a.has(id) ? 'a' : b.has(id) ? 'b' : 'pool'].append(card);
      let suppressClick = false;
      card.addEventListener('dragstart', () => { suppressClick = true; });
      card.addEventListener('dragend', () => { setTimeout(() => { suppressClick = false; }, 500); });
      card.addEventListener('click', () => {
        if (suppressClick) return;
        const current = card.closest('[data-category]').dataset.category;
        containers[current === 'pool' ? 'a' : current === 'a' ? 'b' : 'pool'].append(card);
        queueSave(); card.focus();
      });
    });
    bindSplitDrag(board);
    return board;
  }

  function makeSplitZone(titleText, category, extraClass = '') {
    const column = document.createElement('section');
    column.className = `split-column ${extraClass}`.trim(); column.dataset.category = category;
    const title = document.createElement('h3'); title.textContent = titleText;
    const options = document.createElement('div'); options.className = 'split-options';
    column.append(title, options);
    return column;
  }

  function bindSplitDrag(board) {
    let dragged = null;
    board.addEventListener('dragstart', event => {
      dragged = event.target.closest('.split-person');
      if (!dragged) return;
      dragged.classList.add('is-dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', dragged.dataset.id);
    });
    board.querySelectorAll('.split-column').forEach(zone => {
      zone.addEventListener('dragover', event => { event.preventDefault(); zone.classList.add('is-over'); });
      zone.addEventListener('dragleave', event => { if (!zone.contains(event.relatedTarget)) zone.classList.remove('is-over'); });
      zone.addEventListener('drop', event => {
        event.preventDefault(); zone.classList.remove('is-over');
        if (dragged) zone.querySelector('.split-options').append(dragged);
        queueSave();
      });
    });
    board.addEventListener('dragend', () => {
      dragged?.classList.remove('is-dragging');
      board.querySelectorAll('.is-over').forEach(zone => zone.classList.remove('is-over'));
      dragged = null;
    });
  }

  function readAnswer() {
    const form = stage.querySelector('.question-card');
    const question = questions[index];
    if (!form) return null;
    if (question.type === 'ranking') return {answer_json:{ordered_participant_ids:[...form.querySelectorAll('.ranking-item')].map(item=>item.dataset.id),lap_time:form.elements.lap_time?.value.trim() || ''}};
    if (question.type === 'binary_split') {
      const category_a=[...form.querySelectorAll('[data-category="a"] .split-person')].map(card => card.dataset.id);
      const category_b=[...form.querySelectorAll('[data-category="b"] .split-person')].map(card => card.dataset.id);
      return {answer_json:{category_a,category_b}};
    }
    if (question.type === 'compare_two' || question.type === 'compare_three' || question.type === 'choose_one') return {answer_json:{selected_participant_id:form.elements.selected_participant_id?.value || '',comment:form.elements.comment?.value.trim() || ''}};
    if (question.type === 'slider') return {answer_number:Number(form.elements.answer_number.value)};
    return {answer_text:form.elements.answer_text?.value.trim() || ''};
  }

  function valid() {
    const question=questions[index], answer=readAnswer(), error=stage.querySelector('.form-error'); let ok=true;
    if (question.type === 'compare_two' || question.type === 'compare_three' || question.type === 'choose_one') ok=Boolean(answer.answer_json.selected_participant_id);
    else if (question.type === 'binary_split') ok=answer.answer_json.category_a.length + answer.answer_json.category_b.length === candidatesOf(question).length;
    else if (question.type === 'ranking') ok=Boolean(answer.answer_json.lap_time);
    else if (question.type !== 'ranking' && question.type !== 'slider') ok=Boolean(answer.answer_text);
    error.textContent='Il manque une réponse.'; error.hidden=ok; return ok;
  }

  function queueSave() {
    clearTimeout(saveTimer);
    const question = questions[index];
    if (question?.type === 'binary_split' && stage.querySelector('[data-category="pool"] .split-person')) {
      setSaveStatus('idle', 'Tri en cours');
      return;
    }
    setSaveStatus('saving','Sauvegarde…'); saveTimer=setTimeout(()=>save(false),450);
  }
  function setSaveStatus(state,text) { if (!saveStatus) return; saveStatus.className=`save-status ${state==='idle'?'':`is-${state}`}`; saveStatus.lastChild.textContent=` ${text}`; }

  async function save(requireValid=true) {
    if (requireValid && !valid()) return false;
    const question=questions[index], answer=readAnswer();
    try {
      let answerValue = answer.answer_json ?? answer.answer_number ?? answer.answer_text;
      if (question.type === 'compare_two' || question.type === 'compare_three' || question.type === 'choose_one') {
        answerValue = {selectedParticipantId: answerValue.selected_participant_id, comment: answerValue.comment};
      } else if (question.type === 'ranking') {
        answerValue = {orderedParticipantIds: answerValue.ordered_participant_ids, lapTime: answerValue.lap_time};
      } else if (question.type === 'binary_split') {
        answerValue = {categoryA: answerValue.category_a, categoryB: answerValue.category_b};
      }
      const reviewQuery = reviewMode ? '?review=1' : '';
      const response=await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/answers${reviewQuery}`,{method:'POST',headers:{'Accept':'application/json','Content-Type':'application/json'},body:JSON.stringify({question_instance_id:questionId(question),questionInstanceId:questionId(question),answer:answerValue,...answer})});
      if (!response.ok) throw new Error();
      answers.set(String(questionId(question)),answer.answer_json ?? answer.answer_number ?? answer.answer_text); setSaveStatus('idle','Réponse sauvegardée'); return true;
    } catch (_) { setSaveStatus('error','Sauvegarde impossible'); stage.querySelector('.form-error').textContent='La réponse n’a pas pu être sauvegardée. Réessaie.'; stage.querySelector('.form-error').hidden=false; return false; }
  }

  async function go(direction) {
    clearTimeout(saveTimer); next.disabled=previous.disabled=true;
    if (direction < 0) {
      if (valid() && !(await save(false))) { next.disabled=false; previous.disabled=index===0; return; }
      index=Math.max(0,index-1); render(); window.scrollTo({top:app.offsetTop-20,behavior:'smooth'}); return;
    }
    if (!(await save(true))) { next.disabled=false; previous.disabled=index===0; return; }
    if (direction > 0 && index === questions.length-1) return complete();
    index=Math.max(0,Math.min(questions.length-1,index+direction)); render(); window.scrollTo({top:app.offsetTop-20,behavior:'smooth'});
  }

  async function complete() {
    setSaveStatus('saving','Finalisation…');
    try { const response=await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/complete`,{method:'POST',headers:{'Accept':'application/json'}}); if (!response.ok) throw new Error(); const payload=await response.json().catch(()=>({})); window.location.assign(payload.redirectUrl || payload.redirect_url || `/merci/${encodeURIComponent(sessionId)}`); }
    catch (_) { setSaveStatus('error','Finalisation impossible'); next.disabled=false; previous.disabled=false; }
  }

  async function saveAndReload() {
    clearTimeout(saveTimer);
    next.disabled = true;
    if (await save(true)) {
      setSaveStatus('idle', 'Réponse enregistrée');
      window.setTimeout(() => window.location.reload(), 250);
      return;
    }
    next.disabled = false;
  }

  previous.addEventListener('click',()=>go(-1)); next.addEventListener('click',()=>reviewMode ? saveAndReload() : go(1));
  reviewSelect?.addEventListener('change', async event => {
    const nextIndex = Number(event.currentTarget.value);
    if (!Number.isInteger(nextIndex) || nextIndex === index) return;
    clearTimeout(saveTimer);
    if (!valid() || !(await save(false))) {
      event.currentTarget.value = String(index);
      return;
    }
    index = nextIndex;
    render();
    window.scrollTo({top: app.offsetTop - 20, behavior: 'smooth'});
  });
  document.addEventListener('keydown',event=>{ if(event.ctrlKey && event.key==='Enter'){event.preventDefault();go(1);} });
  load();
})();
