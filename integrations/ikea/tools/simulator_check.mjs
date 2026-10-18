import {mkdirSync,writeFileSync} from 'node:fs';
// Official simulator + actual core. Use a fresh isolated log directory. No paid calls.
const CORE=process.env.CORE || 'http://127.0.0.1:8797',SIM=process.env.SIM || 'http://127.0.0.1:9897',OUT=process.env.OUT || 'docs/evidence/ikea';
mkdirSync(OUT,{recursive:true});const checks=[];const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function get(path,sim=false){const r=await fetch((sim?SIM:CORE)+path);if(!r.ok)throw Error(path+' '+r.status);return r.json();}
async function post(path,body,sim=false){const r=await fetch((sim?SIM:CORE)+path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw Error(path+' '+r.status+' '+await r.text());return r.json();}
async function input(action){await post('/api/input',{action},true);await wait(650);}
async function check(name,test){await wait(1000);const h=await get('/hud');if(!test(h))throw Error(name+': '+JSON.stringify(h));const r=await fetch(SIM+'/api/screenshot/glasses');if(!r.ok)throw Error('screenshot failed');writeFileSync(OUT+'/sim-'+name+'.png',Buffer.from(await r.arrayBuffer()));checks.push({name,frame:h});console.log('PASS',name,h.mode,h.cue?.line1);}
try{
await fetch(SIM+'/api/ping');
const initial=await get('/session');
await post('/session/goal',{session_id:initial.id,mode:'build',via:'phone_text',text:'I have a white IKEA desk with a drawer and cabinet'});
await check('01-photo-shortlist',h=>h.mode==='visual'&&h.image.guide_id==='product_matches');
await input('down');await check('02-highlight-second',h=>h.image.guide_id==='product_matches'&&h.cue.line1.startsWith('2/'));
await input('up');await input('click');await check('03-full-product-photo',h=>h.mode==='visual'&&h.image.guide_id.includes('80213074'));
await input('up');await check('04-back-to-photo-shortlist',h=>h.image.guide_id==='product_matches');
await input('click');await wait(700);await input('click');await check('05-cabinet-question',h=>h.mode==='menu'&&h.menu.prompt==='CABINET SIDE?');
await input('click');await check('06-first-step',h=>h.mode==='visual'&&h.step.index===0&&h.image.view==='where');
const sess=await get('/session');await post('/ask',{session_id:sess.id,text:'Show me step 14'});
await check('07-manual-step14',h=>h.step?.index===13&&h.image?.view==='where');
await input('click');await check('08-manual-parts',h=>h.mode==='visual'&&h.image.view==='how');
await input('click');await check('09-back-to-default-diagram',h=>h.mode==='visual'&&h.image.view==='where'&&h.step?.index===13);
const parts=await post('/ask',{session_id:sess.id,text:'Which fastener do I use?'});if(!parts.text.includes('103430')||!parts.text.includes('110126'))throw Error('parts answer');
await post('/ask',{session_id:sess.id,text:'Show me a closer look'});await check('10-closeup-stays-open',h=>h.mode==='visual'&&h.image.view==='how');
await input('down');await check('11-confirm-next',h=>h.step?.index===14);
const logs=(await get('/api/console',true)).entries;const imageMetrics=logs.filter(e=>e.message.includes('image metrics'));
const errors=logs.filter(e=>e.level==='error'||e.message.includes('[uncaught]')||e.message.includes('[unhandledrejection]'));
if(errors.length)throw Error('simulator errors '+JSON.stringify(errors));
writeFileSync(OUT+'/simulator-result.json',JSON.stringify({status:'PASS',scope:'Official simulator 0.9.5; actual core; cached product photos and manual; no physical G2 or microphone',checks,logs},null,2));
console.log('PASS',checks.length,'checks; zero simulator console errors');
}catch(error){writeFileSync(OUT+'/simulator-result.json',JSON.stringify({status:'FAIL',error:String(error),checks},null,2));throw error;}
