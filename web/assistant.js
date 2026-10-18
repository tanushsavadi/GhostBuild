/* One conversation per step. Answers never replace the step/diagram workspace. */
(function () {
  'use strict';
  var $=function(id){return document.getElementById(id);};
  if(!$('sec-chat')||!window.GBStepHelp||new URLSearchParams(location.search).get('fixture'))return;
  var H=window.GBStepHelp, core=(new URLSearchParams(location.search).get('core')||'').replace(/\/+$/,'');
  var S={st:null,firstLoad:true,sending:false,session:null,spoken:{},renderKey:'',online:true};
  var GROUND={guide:'From the guide',general:'General knowledge · check against your manual',unsure:'Not sure · check the source'};
  function el(tag,cls,text){var n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
  function get(path){return fetch(core+path,{cache:'no-store',signal:AbortSignal.timeout(3000)}).then(function(r){if(!r.ok)throw Error(String(r.status));return r.json();});}
  function post(path,body){return fetch(core+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(async function(r){var j=await r.json();if(!r.ok)throw Error(j.detail||'Message was not sent.');return j;});}
  function render(){
    var st=S.st, current=st&&st.current_step, rows=H.messages(st), waiting=H.pending(st), sec=$('sec-chat');
    sec.hidden=!(st&&(current||rows.length||waiting));
    if(sec.hidden)return;
    $('h-chat').textContent=current?'Questions on this step':'Conversation';
    $('chat-form').hidden=!!current;
    $('chat-typing').hidden=!waiting;
    var description=current?'Step '+(current.index+1)+' · '+current.title:'Tell me what you need';
    $('help-context').textContent=description;
    $('help-return').hidden=!current;
    $('help-status').textContent=!S.online?'Connection lost. Your step stays here.':waiting?'Thinking about this step…':current?'Ask anytime. Your place is kept.':'';
    $('help-status').classList.toggle('thinking',waiting);
    var key=JSON.stringify([rows,current,waiting,S.online]);
    if(key!==S.renderKey){
      S.renderKey=key;var log=$('chat-log'),atBottom=log.scrollHeight-log.scrollTop-log.clientHeight<50;log.replaceChildren();
      rows.forEach(function(m){var b=el('div','bubble '+m.role);b.appendChild(el('div','bubble-text',m.text));
        if(m.role==='assistant'&&m.kind==='step')b.appendChild(el('div','bubble-tag g-'+m.grounding,(m.cached?'Saved answer · ':'')+(GROUND[m.grounding]||'From the guide')));
        log.appendChild(b);});
      if(!rows.length)log.appendChild(el('p','meta','Ask about a part, a diagram, or anything unclear. I’ll keep this conversation with the step.'));
      if(atBottom)log.scrollTop=log.scrollHeight;
      var chips=$('chat-chips');chips.replaceChildren();var last=rows[rows.length-1];
      if(last&&last.role==='assistant'&&!waiting)(last.quick_replies||[]).forEach(function(q){var b=el('button','qchip',q);b.type='button';b.addEventListener('click',function(){send(q);});chips.appendChild(b);});
    }
    window.dispatchEvent(new CustomEvent('ghostbuild:step-help',{detail:{current:current,pending:waiting,message:H.answer(st)}}));
  }
  function speakNew(){
    var st=S.st;if(!st)return;var tts=$('tts-enabled');
    (st.messages||[]).forEach(function(m){var key=m.id||[m.at,m.role,m.kind,m.text].join('|');if(S.spoken[key])return;S.spoken[key]=true;
      if(!S.firstLoad&&m.role==='assistant'&&m.speak&&tts&&tts.checked&&!tts.disabled&&(!m.step_id||H.same(m,st.current_step)))window.dispatchEvent(new CustomEvent('ghostbuild:answer',{detail:{text:m.text,from:'assistant'}}));});
    S.firstLoad=false;
  }
  function send(text){
    text=String(text||'').trim();if(!text||S.sending||!S.session||!S.online)return;
    if(S.session.phase==='task'){$('ask-text').value=text;$('ask-form').requestSubmit();return;}
    S.sending=true;window.dispatchEvent(new Event('ghostbuild:input'));
    post('/session/goal',{session_id:S.session.id,mode:window.GBLogic?window.GBLogic.inferMode(text):'build',via:'phone_text',text:text})
      .then(function(){$('chat-input').value='';return refresh();})
      .catch(function(e){$('help-status').textContent=e.message;}).finally(function(){S.sending=false;});
  }
  function refresh(){return Promise.all([get('/assistant/state'),get('/session')]).then(async function(r){
      var next=r[0].current_step, previous=S.st&&S.st.current_step;
      if(!H.same(next,previous)&&window.GBWorkspace)await window.GBWorkspace.refresh();
      var changed=JSON.stringify(r[0])!==JSON.stringify(S.st)||JSON.stringify(r[1])!==JSON.stringify(S.session)||!S.online;S.st=r[0];S.session=r[1];S.online=true;
      if(changed){render();speakNew();window.dispatchEvent(new CustomEvent('ghostbuild:assistant',{detail:S.st}));}})
    .catch(function(){if(S.online){S.online=false;render();}});}
  function loop(){refresh().then(function(){setTimeout(loop,H.pending(S.st)?350:900);});}
  $('chat-form').addEventListener('submit',function(e){e.preventDefault();send($('chat-input').value);});
  $('ask-anytime-link').addEventListener('click',function(){$('ask-text').focus();$('h-ask').scrollIntoView({behavior:'smooth',block:'nearest'});});
  $('help-return').addEventListener('click',function(){
    var current=S.st&&S.st.current_step;if(!current||!S.session)return;
    post('/assistant/dismiss',{session_id:S.session.id,card_id:current.card_id,step_id:current.step_id})
      .then(function(){$('h-playbook').focus({preventScroll:true});$('h-playbook').scrollIntoView({behavior:'smooth',block:'nearest'});})
      .catch(function(e){$('help-status').textContent=e.message;});
  });
  window.addEventListener('ghostbuild:asked',refresh);
  window.GBAssistant={state:function(){return S.st;},notesFor:function(cardId,stepId){return ((S.st&&S.st.notes)||[]).filter(function(n){return n.card_id===cardId&&n.step_id===stepId;});}};
  loop();
})();
