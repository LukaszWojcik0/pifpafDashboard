import assert from 'node:assert/strict';
import test from 'node:test';

import { calculateCumulativePlayers } from '../app/playerCounts.mjs';

test('counts players from simple max/current availability', () => {
  assert.equal(calculateCumulativePlayers(100, [], 99), 1);
  assert.equal(calculateCumulativePlayers(40, [], 4), 36);
});

test('does not decrease players when available pool is reset', () => {
  assert.equal(calculateCumulativePlayers(40, [4, 40, 39], 39), 37);
});

test('ignores unknown measurements in history', () => {
  assert.equal(calculateCumulativePlayers(10, [10, null, 8, undefined, 10, 9], 9), 3);
});

test('returns null when max or current value is not reliable', () => {
  assert.equal(calculateCumulativePlayers(null, [], 9), null);
  assert.equal(calculateCumulativePlayers(10, [], 11), null);
});
