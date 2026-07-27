import assert from 'node:assert/strict';
import test from 'node:test';
import {
  classifyEvent,
  eventVisibilityReason,
  isPastEvent,
  isUncertainEvent,
} from '../app/eventVisibility.mjs';

const now = new Date(2026, 6, 27, 12, 0, 0);

function event(overrides = {}) {
  return {
    title: 'Warzone',
    event_date: '2026-08-01',
    status: 'available',
    current_available: 10,
    ...overrides,
  };
}

test('public events must be known and upcoming', () => {
  assert.equal(classifyEvent(event(), now), 'public');
});

test('unknown or incomplete events require admin review', () => {
  assert.equal(isUncertainEvent(event({ title: 'Nieznane wydarzenie' })), true);
  assert.equal(isUncertainEvent(event({ event_date: 'Unknown Date' })), true);
  assert.equal(isUncertainEvent(event({ status: 'unknown' })), true);
  assert.equal(isUncertainEvent(event({ current_available: null })), true);
  assert.equal(classifyEvent(event({ event_date: null }), now), 'needs_review');
  assert.match(eventVisibilityReason(event({ event_date: null }), now), /daty/);
});

test('past events are hidden from the public dashboard', () => {
  assert.equal(isPastEvent(event({ event_date: '2026-07-26' }), now), true);
  assert.equal(classifyEvent(event({ event_date: '2026-07-26' }), now), 'past');
});
