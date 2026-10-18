import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),L=require('../discovery.js');
test('cached provenance never claims a live search',()=>{assert.match(L.provenance({record:{how:'cache',verified_at:1792300000000}}),/^Cached;/);});
test('live search labelled distinctly',()=>{assert.match(L.provenance({record:{how:'live_search',verified_at:1792300000000}}),/^Live official-site search;/);});
test('up to five genuine records without filling slots',()=>{assert.equal(L.candidates({candidates:[1,2]}).length,2);assert.equal(L.candidates({candidates:[1,2,3,4,5,6]}).length,5);});
test('local photo path encodes identifiers',()=>{assert.equal(L.asset({source:'retailer',article:'123'}),'/discovery/img/retailer/123.png');assert.match(L.asset({source:'../x',article:'a/b'}),/%2F/);});
test('unsafe links rejected',()=>{assert.equal(L.safeLink('javascript:alert(1)'),'');assert.equal(L.safeLink('https://www.ikea.com/a'),'https://www.ikea.com/a');});
