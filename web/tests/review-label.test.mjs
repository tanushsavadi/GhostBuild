import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const L = createRequire(import.meta.url)('../logic.js');

test('prepared AI guide is unreviewed even without a live research record', () => {
  const note = L.reviewNotice({ card_id: 'prepared', review: 'AI-compiled; not human-reviewed.' }, { unreviewed_cards: [] });
  assert.match(note, /not been reviewed by a human/);
  assert.doesNotMatch(note, /live/i);
});

test('a live draft retains its backend review notice', () => {
  assert.equal(L.reviewNotice({ card_id: 'draft' }, { unreviewed_cards: ['draft'], note: 'Unreviewed live research.' }), 'Unreviewed live research.');
});

test('authored and human-reviewed cards do not acquire an AI draft label', () => {
  assert.equal(L.reviewNotice({ card_id: 'authored' }, null), '');
  assert.equal(L.reviewNotice({ card_id: 'reviewed', review: 'Reviewed against the manufacturer manual.' }, { unreviewed_cards: [] }), '');
  assert.equal(L.reviewNotice(null, null), '');
});
