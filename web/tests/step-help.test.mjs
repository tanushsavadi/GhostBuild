import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),H=require('../step-help.js'),L=require('../logic.js');
const current={card_id:'card',step_id:'s14'};
test('thread keeps answers on the original step',()=>{
 const state={current_step:current,messages:[{role:'assistant',kind:'step',card_id:'card',step_id:'s13',text:'old'},{role:'assistant',kind:'step',...current,text:'current'},{role:'assistant',kind:'intake',text:'intake'}]};
 assert.deepEqual(H.messages(state).map(m=>m.text),['current']);assert.equal(H.answer(state).text,'current');
});
test('an old pending answer never makes the next step look busy',()=>{
 assert.equal(H.pending({current_step:current,pending:'step',pending_step:{card_id:'card',step_id:'s13'}}),false);
 assert.equal(H.pending({current_step:current,pending:'step',pending_step:current}),true);
});
test('intake and step threads remain separate',()=>{
 assert.equal(H.messages({messages:[{kind:'step',text:'step'},{kind:'intake',text:'goal'}]}).length,1);
});
test('pending and cached metadata survive the API adapter',()=>{
 assert.equal(L.normalizeAsk({answer:null,text:'Thinking',intent:'assistant',pending:true,card_id:'c',step_id:'s'}).pending,true);
 assert.equal(L.normalizeAsk({answer:{line1:'A'},text:'Saved',intent:'assistant',cached:true}).cached,true);
});
