/* Product discovery inside the existing goal flow. Pure display helpers are also exported for node tests. */
(function (root) {
  'use strict';
  function provenance(c) {
    if (c.origin) return c.origin;
    var r = c.record || c, date = r.verified_at ? new Date(r.verified_at).toISOString().slice(0, 10) : 'unknown date';
    return (r.how === 'live_search' ? 'Live official-site search; page read ' : 'Cached; read from official site ') + date;
  }
  function candidates(s) { return (s.candidates || []).slice(0, 5); }
  function asset(r) { return '/discovery/img/' + encodeURIComponent(r.source) + '/' + encodeURIComponent(r.article) + '.png'; }
  function safeLink(url) { try { return new URL(url).protocol === 'https:' ? url : ''; } catch (_) { return ''; } }
  var logic = {provenance:provenance, candidates:candidates, asset:asset, safeLink:safeLink};
  if (typeof module !== 'undefined' && module.exports) module.exports = logic;
  if (!root.document) return;
  root.GBDiscoveryLogic = logic;
  var doc = root.document, sec = doc.getElementById('sec-discovery');
  if (!sec || new URLSearchParams(location.search).get('fixture')) return;
  var core = (new URLSearchParams(location.search).get('core') || '').replace(/\/+$/, '');
  var state, key, busy = false, online = true;
  function el(tag, cls, text) { var n = doc.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
  function btn(text, action) { var b = el('button','ghost',text); b.type = 'button'; b.disabled = busy || !online; b.addEventListener('click',action); return b; }
  function post(action, body) {
    if (busy || !state || !online) return Promise.resolve();
    busy = true; doc.getElementById('discovery-error').textContent=''; render();
    return fetch(core + '/discovery/' + action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({session_id:state.session_id},body || {}))})
      .then(function (r) { if (!r.ok) return r.json().then(function(j) {throw new Error(j.detail || 'Selection could not be sent.');}); return r.json(); })
      .then(function (s) { state = s; key = ''; })
      .catch(function(e) { doc.getElementById('discovery-error').textContent=e.message; })
      .finally(function () { busy=false; render(); });
  }
  function link(text,url) { var n=el('a','',text); n.href=safeLink(url); n.target='_blank'; n.rel='noopener noreferrer'; return n; }
  function render() {
    sec.hidden = !(state && state.phase !== 'idle' && state.enabled !== false);
    if (sec.hidden) return;
    sec.classList.toggle('discovery-ready', state.phase === 'ready');
    doc.getElementById('h-discovery').textContent = state.phase === 'ready' ? 'Your product & manual' : 'Which product do you have?';
    var box=doc.getElementById('discovery-content'); box.replaceChildren();
    box.appendChild(el('p','discovery-message',state.message));
    if (!online) box.appendChild(el('p','res err','Connection lost. Reconnect to select; saved choices remain visible.'));
    if (state.live_state === 'running') box.appendChild(el('p','meta','Searching the official site… Saved matches below remain available.'));
    if (state.notice) box.appendChild(el('p','meta',state.notice));
    var grid=el('div','product-grid');
    if (['choosing','confirming','asking','searching'].indexOf(state.phase)>=0) candidates(state).forEach(function(c) {
      var r=c.record, card=el('article','product-card'), image=el('img','product-photo');
      image.src=core+asset(r); image.alt=r.name+' '+r.type_name+' '+r.color; image.loading='eager';
      image.addEventListener('error',function(){ image.hidden=true; }); card.appendChild(image);
      card.appendChild(el('h3','',c.rank+'. '+r.name));
      card.appendChild(el('p','', [r.type_name,r.color,r.size].filter(Boolean).join(' · ')));
      card.appendChild(el('p','article-number','Article '+(r.article_display || r.article)));
      if (r.manual_verified) card.appendChild(el('span','product-chip','Official manual verified'));
      (c.matched || []).forEach(function(t){card.appendChild(el('span','product-chip','Matches: '+t));});
      (c.unverified || []).forEach(function(t){card.appendChild(el('span','product-chip unknown','Unverified: '+t));});
      (c.conflicts || []).forEach(function(t){card.appendChild(el('span','product-chip unknown','Differs: '+t));});
      card.appendChild(el('p','meta',provenance(c)));
      card.appendChild(btn(state.phase==='confirming'?'Yes, this is mine':'Choose '+r.name,function(){post('select',{article:r.article});}));
      card.appendChild(link('Official product page',r.product_url)); grid.appendChild(card);
    });
    box.appendChild(grid);
    if (state.question) {
      box.appendChild(el('h3','',state.question.prompt));
      state.question.options.forEach(function(o){box.appendChild(btn(o,function(){post('refine',{text:o});}));});
    }
    if (state.phase==='configuring' && state.config_question) {
      var q=state.config_question; box.appendChild(el('h3','',q.prompt)); box.appendChild(el('p','meta',q.help));
      var configs=el('div','config-grid');
      q.options.forEach(function(o){var b=btn(o.label,function(){post('config',{option:o.id});}); b.setAttribute('aria-label',o.label);
        if (o.image && o.image.indexOf('/discovery/assets/')===0) {var im=el('img','config-photo');im.src=core+o.image;im.alt=o.label+' from the official manual';b.prepend(im);} configs.appendChild(b);});box.appendChild(configs);
    }
    if (state.selected) {
      box.appendChild(el('p','meta','Selected: '+state.selected.name+' · '+state.selected.article+' · '+Object.values(state.config || {}).join(', ')));
      if (state.selected.manual_verified && state.selected.manual_url) box.appendChild(link('Open the official assembly manual',state.selected.manual_url));
      if (state.phase==='ready') box.appendChild(el('p','meta','Diagrams: official manufacturer manual. Authored step text still needs a human spot-check against the PDF.'));
    }
    var active=state.phase!=='ready';
    doc.getElementById('discovery-actions').hidden=!active;
    doc.getElementById('discovery-form').hidden=!active;
    if (active && !state.question && state.phase!=='configuring') box.appendChild(btn('None of these / Refine',function(){post('none');}));
    if (active && state.phase!=='configuring' && (state.candidates || []).length) {
      box.appendChild(btn('Show more saved matches',function(){post('more');}));
      box.appendChild(btn('Search the official site again',function(){post('refresh');}));
    }
    var t=state.timings || {}, timings=[];
    ['cache','exact','search','validate','total'].forEach(function(k){if (t[k+'_ms'] !== undefined && t[k+'_ms'] !== null) timings.push(k+' '+t[k+'_ms']+' ms');});
    if (timings.length) box.appendChild(el('p','meta discovery-timings','Measured: '+timings.join(' · ')));
    if (t.provider) box.appendChild(el('p','meta',t.provider));
    sec.querySelectorAll('button, input').forEach(function(b){b.disabled=busy || !online;});
  }
  async function refresh() {
    try {
      var r=await fetch(core+'/discovery/state',{cache:'no-store',signal:AbortSignal.timeout(3000)});
      if (!r.ok) throw new Error('discovery unavailable');
      var s=await r.json(), next=JSON.stringify(s); var changed=next!==key || !online;
      online=true; state=s;
      if (changed) {key=next;render();}
    } catch(e) {if (online) {online=false;render();}}
  }
  doc.getElementById('discovery-form').addEventListener('submit',function(e){e.preventDefault();var input=doc.getElementById('discovery-input'),text=input.value.trim();if(text) post('refine',{text:text}).then(function(){input.value='';});});
  doc.getElementById('discovery-cancel').addEventListener('click',function(){post('cancel');});
  root.addEventListener('ghostbuild:asked',refresh);
  async function loop(){await refresh();setTimeout(loop,700);} loop();
})(typeof window !== 'undefined' ? window : globalThis);
