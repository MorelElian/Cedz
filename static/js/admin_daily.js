(() => {
  const app=document.querySelector('[data-admin-app]');if(!app)return;
  const esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';
  const repeatWarnings={};
  async function api(path,options={}){const response=await fetch(path,{...options,headers:{Accept:'application/json','Content-Type':'application/json','X-CSRF-Token':csrf,...options.headers}});const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error||'Opération impossible.');return data;}
  async function load(){
    try{
      const [suggestions,daily,questions]=await Promise.all([api('/api/admin/question-suggestions'),api('/api/admin/daily-questions'),api('/api/admin/questions')]);
      const sroot=app.querySelector('[data-suggestion-list]');const pending=(suggestions.suggestions||[]).filter(item=>item.status==='submitted');
      sroot.innerHTML=pending.length?pending.map(item=>'<article class="answer-card"><header><span>Par <strong>'+esc(item.authorName)+'</strong> · '+esc(item.type)+'</span></header><h3>'+esc(item.body)+'</h3><footer><button class="button button-secondary button-small" data-suggestion-action="approved" data-suggestion-id="'+esc(item.id)+'">Approuver</button><button class="button button-ghost button-small" data-suggestion-action="rejected" data-suggestion-id="'+esc(item.id)+'">Refuser</button></footer></article>').join(''):'<div class="empty-state compact-empty"><strong>Rien à examiner.</strong></div>';
      const droot=app.querySelector('[data-daily-list]');
      const options=(questions.questions||[]).filter(q=>q.isActive&&['free_text','compare_two','compare_three','choose_one','slider'].includes(q.type)).map(q=>'<option value="'+esc(q.id)+'">'+esc(q.title)+'</option>').join('');
      droot.innerHTML=(daily.dailyQuestions||[]).map(item=>'<article class="answer-card"><header><strong>'+esc(item.participantName)+'</strong></header><small>Question actuellement envoyée</small><h3>'+esc(item.question?.body||'Aucune — attente du prochain envoi')+'</h3>'+(item.nextQuestion?'<small>Prochaine question préparée</small><p>'+esc(item.nextQuestion.body)+'</p>':'')+((repeatWarnings[item.participantId]||item.nextQuestion?.alreadyGenerated)?'<p class="daily-repeat-warning" role="status"><strong>Attention :</strong> cette question a déjà été générée pour cette personne.</p>':'')+'<label class="field"><span>Préparer la prochaine question</span><select data-question-choice><option value="">Tirage aléatoire</option>'+options+'</select></label><button class="button button-secondary button-small" data-regenerate="'+esc(item.participantId)+'">Préparer / changer la suivante</button></article>').join('');
    }catch(error){app.querySelector('[data-suggestion-list]').textContent=error.message;}
  }
  app.addEventListener('click',async event=>{const b=event.target.closest('button');if(!b)return;try{if(b.dataset.suggestionId){await api('/api/admin/question-suggestions/'+b.dataset.suggestionId,{method:'PATCH',body:JSON.stringify({status:b.dataset.suggestionAction})});await load();}if(b.dataset.regenerate){const selected=b.closest('article').querySelector('[data-question-choice]').value;const result=await api('/api/admin/daily-questions/'+b.dataset.regenerate+'/regenerate',{method:'POST',body:JSON.stringify({questionId:selected||null})});repeatWarnings[b.dataset.regenerate]=Boolean(result.alreadyGenerated);await load();}if(b.matches('[data-reload-daily]'))await load();}catch(error){window.alert(error.message);}});
  load();
})();
