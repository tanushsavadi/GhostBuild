/* Step ownership is shared by the answer panel and its tests. No DOM or network. */
(function(root){
  'use strict';
  function same(a,b){return !!(a&&b&&a.card_id===b.card_id&&a.step_id===b.step_id);}
  function messages(state){var current=state&&state.current_step;return ((state&&state.messages)||[]).filter(function(m){return current ? m.kind==='step'&&same(m,current) : m.kind!=='step';});}
  function pending(state){return !!(state&&state.pending&&(state.pending!=='step'||same(state.pending_step,state.current_step)));}
  function answer(state){var rows=messages(state);for(var i=rows.length-1;i>=0;i--)if(rows[i].role==='assistant'||rows[i].role==='system')return rows[i];return null;}
  var api={same:same,messages:messages,pending:pending,answer:answer};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.GBStepHelp=api;
})(typeof window!=='undefined'?window:globalThis);
