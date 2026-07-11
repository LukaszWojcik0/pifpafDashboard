import crypto from 'node:crypto';

export const AUTH_LIMITS = Object.freeze({
  usernameMin: 3,
  usernameMax: 64,
  passwordMin: 8,
  passwordMax: 256,
  setupTokenMax: 256,
  loginWindowMs: 15 * 60 * 1000,
  loginMaxAttempts: 5,
});

export function normalizeAuthInput(value) {
  return typeof value === 'string' ? value.trim() : '';
}

export function validateCredentials(username, password) {
  if (username.length < AUTH_LIMITS.usernameMin || username.length > AUTH_LIMITS.usernameMax) {
    return `Login musi mieć od ${AUTH_LIMITS.usernameMin} do ${AUTH_LIMITS.usernameMax} znaków.`;
  }
  if (password.length < AUTH_LIMITS.passwordMin || password.length > AUTH_LIMITS.passwordMax) {
    return `Hasło musi mieć od ${AUTH_LIMITS.passwordMin} do ${AUTH_LIMITS.passwordMax} znaków.`;
  }
  return null;
}

export function shouldRequireSetupToken(env = process.env) {
  return env.NODE_ENV === 'production' || Boolean(env.ADMIN_SETUP_TOKEN);
}

export function isSecureCookieEnabled(env = process.env) {
  return env.NODE_ENV === 'production';
}

function constantTimeEqual(value, expected) {
  const valueHash = crypto.createHash('sha256').update(value).digest();
  const expectedHash = crypto.createHash('sha256').update(expected).digest();
  return crypto.timingSafeEqual(valueHash, expectedHash);
}

export function verifySetupToken(submittedToken, env = process.env) {
  const submitted = normalizeAuthInput(submittedToken);
  const expected = normalizeAuthInput(env.ADMIN_SETUP_TOKEN);
  const tokenRequired = shouldRequireSetupToken(env);

  if (!tokenRequired) return { ok: true };
  if (!expected) return { ok: false, reason: 'Brak ADMIN_SETUP_TOKEN w konfiguracji produkcyjnej.' };
  if (!submitted || submitted.length > AUTH_LIMITS.setupTokenMax) {
    return { ok: false, reason: 'Nieprawidłowy token pierwszej konfiguracji.' };
  }
  if (!constantTimeEqual(submitted, expected)) {
    return { ok: false, reason: 'Nieprawidłowy token pierwszej konfiguracji.' };
  }
  return { ok: true };
}

export class FixedWindowRateLimiter {
  constructor({ maxAttempts, windowMs, now = () => Date.now() }) {
    this.maxAttempts = maxAttempts;
    this.windowMs = windowMs;
    this.now = now;
    this.attempts = new Map();
  }

  isLimited(key) {
    const entry = this.attempts.get(key);
    if (!entry) return false;
    if (entry.resetAt <= this.now()) {
      this.attempts.delete(key);
      return false;
    }
    return entry.count >= this.maxAttempts;
  }

  recordFailure(key) {
    const current = this.attempts.get(key);
    const now = this.now();
    if (!current || current.resetAt <= now) {
      this.attempts.set(key, { count: 1, resetAt: now + this.windowMs });
      return;
    }
    current.count += 1;
  }

  clear(key) {
    this.attempts.delete(key);
  }
}

export const loginRateLimiter = new FixedWindowRateLimiter({
  maxAttempts: AUTH_LIMITS.loginMaxAttempts,
  windowMs: AUTH_LIMITS.loginWindowMs,
});
