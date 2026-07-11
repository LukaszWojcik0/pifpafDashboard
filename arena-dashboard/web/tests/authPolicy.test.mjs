import assert from 'node:assert/strict';
import test from 'node:test';
import {
  AUTH_LIMITS,
  FixedWindowRateLimiter,
  isSecureCookieEnabled,
  validateCredentials,
  verifySetupToken,
} from '../app/authPolicy.mjs';

test('validates login and password lengths', () => {
  assert.equal(validateCredentials('admin', 'long-enough-password'), null);
  assert.match(validateCredentials('ab', 'long-enough-password'), /Login/);
  assert.match(validateCredentials('a'.repeat(AUTH_LIMITS.usernameMax + 1), 'long-enough-password'), /Login/);
  assert.match(validateCredentials('admin', 'short'), /Hasło/);
  assert.match(validateCredentials('admin', 'x'.repeat(AUTH_LIMITS.passwordMax + 1)), /Hasło/);
});

test('uses secure cookies only in production', () => {
  assert.equal(isSecureCookieEnabled({ NODE_ENV: 'production' }), true);
  assert.equal(isSecureCookieEnabled({ NODE_ENV: 'development' }), false);
});

test('requires a matching setup token in production', () => {
  assert.deepEqual(verifySetupToken('secret', { NODE_ENV: 'production', ADMIN_SETUP_TOKEN: 'secret' }), { ok: true });
  assert.equal(verifySetupToken('wrong', { NODE_ENV: 'production', ADMIN_SETUP_TOKEN: 'secret' }).ok, false);
  assert.equal(verifySetupToken('', { NODE_ENV: 'production' }).ok, false);
});

test('rate limiter blocks after configured failed attempts and resets', () => {
  let now = 1000;
  const limiter = new FixedWindowRateLimiter({ maxAttempts: 2, windowMs: 100, now: () => now });
  assert.equal(limiter.isLimited('user:ip'), false);
  limiter.recordFailure('user:ip');
  assert.equal(limiter.isLimited('user:ip'), false);
  limiter.recordFailure('user:ip');
  assert.equal(limiter.isLimited('user:ip'), true);
  now += 101;
  assert.equal(limiter.isLimited('user:ip'), false);
});
