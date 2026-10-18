/** Guide Studio pure logic against real compiled cards: source matching, routes, evidence, honest labels. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import test from 'node:test';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const S = createRequire(import.meta.url)(path.join(root, 'web/studio-logic.js'));
const load = rel => JSON.parse(readFileSync(path.join(root, rel), 'utf8'));
const bike = load('knowledge/compiled/bike_flat_tire/card.json');
const ikea = load('knowledge/products/ikea/80213074/cards/ikea_80213074_cabinet_left.json');
const row = c => ({card_id: c.card_id, title: c.title, sources: c.sources});

test('normUrl ignores scheme case, www, query, hash and trailing slash; rejects non-http', () => {
  assert.equal(S.normUrl('HTTPS://www.IKEA.com/us/en/p/micke-desk-white-80213074/?x=1#top'), 'ikea.com/us/en/p/micke-desk-white-80213074');
  assert.equal(S.normUrl('javascript:alert(1)'), null);
  assert.equal(S.normUrl('micke desk'), null);
});

test('matchUrl finds the guide compiled from that exact source, else only same-site guides', () => {
  const guides = [row(bike), row(ikea)];
  const m = S.matchUrl(guides, ikea.sources[0].url.replace('https://www.', 'HTTP://') + '?ref=x');
  assert.deepEqual(m.exact.map(x => x.card_id), [ikea.card_id]);
  const site = S.matchUrl(guides, 'https://www.parktool.com/en-us/blog/repair-help/some-other-article');
  assert.equal(site.exact.length, 0);
  assert.deepEqual(site.site.map(x => x.card_id), [bike.card_id]);
  const none = S.matchUrl(guides, 'https://example.com/manual.pdf');
  assert.ok(none.valid && !none.exact.length && !none.site.length);
});

test('routes follow PlaybookEngine rules: choices branch, next jumps, outcome/stop end', () => {
  const rs = S.routes(bike);
  const q = rs.find(r => r.kind === 'question');
  const qs = bike.steps.find(s => s.id === q.id);
  assert.deepEqual(q.to.map(t => t.to), qs.choices.map(c => c.next));
  for (const r of rs.filter(r => r.kind === 'stop' || r.kind === 'outcome')) assert.ok(r.ends && !r.to.length);
  const jumper = bike.steps.findIndex(s => s.kind === 'action' && s.next);
  if (jumper >= 0) assert.equal(rs[jumper].to[0].to, bike.steps[jumper].next);
  const lin = S.routes(ikea);
  assert.equal(lin[0].to[0].to, ikea.steps[1].id);
  assert.deepEqual(S.branchOnly(ikea), {});
});

test('evidence joins each cite with its source and reads manual page numbers', () => {
  const ev = S.evidence(bike, bike.steps.find(s => s.cites.length));
  assert.ok(ev[0].quote && ev[0].url && ev[0].title && ev[0].host === 'parktool.com');
  const st = ikea.steps.find(s => s.cites.some(c => /page/.test(c.url || c.loc || '')));
  const e = S.evidence(ikea, st)[0];
  assert.equal(typeof e.page, 'number');
  assert.equal(e.kind, ikea.sources.find(s => s.id === st.cites[0].source).kind);
  assert.deepEqual(S.evidence(ikea, {cites: []}), []);
});

test('guideLabels never call an AI-compiled guide reviewed', () => {
  const l = S.guideLabels({provenance: 'WEB TUTORIAL', ai_compiled: true, steps: 14, quoted: 14, cited: 14});
  assert.deepEqual(l, ['WEB TUTORIAL', 'AI-COMPILED · NOT HUMAN-REVIEWED', 'EVERY STEP QUOTES ITS SOURCE']);
  assert.ok(!S.guideLabels({provenance: 'MANUFACTURER DOC', steps: 3, cited: 2}).some(x => /REVIEWED|VERIFIED/.test(x)));
});

test('liveView says compiling is off instead of faking progress', () => {
  assert.equal(S.liveView({enabled: false}).state, 'off');
  assert.match(S.liveView({enabled: false}).text, /GB_LIVE_RESEARCH=0/);
  const run = S.liveView({enabled: true, active: {goal: 'fix x', elapsed_s: 12, progress: {fraction: 0.4, stage: 1, stages: ['Search', 'Read']}}});
  assert.deepEqual([run.state, run.stage, run.fraction, run.estimate], ['running', 'Read', 0.4, true]);
  assert.equal(S.liveView({enabled: true, last: {ok: false, goal: 'g', error: 'no official source'}}).state, 'failed');
});

test('frameText mirrors menu, visual and quiet HudFrames', () => {
  const menu = S.frameText({mode: 'menu', menu: {prompt: 'TUBE?', options: ['A', 'B'], selected: 1}, step: {index: 0, count: 14}});
  assert.deepEqual(menu.options, ['  A', '> B']);
  assert.equal(menu.tag, '1/14');
  const vis = S.frameText({mode: 'visual', cue: {line1: 'L1', line2: 'L2'}, image: {index: 1, count: 3, url: '/x.png'}, step: {index: 2, count: 35}});
  assert.equal(vis.kind, 'visual');
  assert.equal(vis.tag, '3/35  PIC 2/3');
  assert.equal(S.frameText({mode: 'quiet'}).kind, 'empty');
  assert.equal(S.frameText(null).kind, 'empty');
});

test('pickId picks the shortlist article / config option that is part of the card id', () => {
  assert.equal(S.pickId('ikea_80213074_cabinet_left', ['10244743', '80213074']), '80213074');
  assert.equal(S.pickId('ikea_80213074_cabinet_left', ['left', 'right']), 'left');
  assert.equal(S.pickId('ikea_80213074_cabinet_left', ['999']), null);
});
