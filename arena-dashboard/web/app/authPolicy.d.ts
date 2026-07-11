export const AUTH_LIMITS: {
  readonly usernameMin: number;
  readonly usernameMax: number;
  readonly passwordMin: number;
  readonly passwordMax: number;
  readonly setupTokenMax: number;
  readonly loginWindowMs: number;
  readonly loginMaxAttempts: number;
};

export function normalizeAuthInput(value: FormDataEntryValue | string | null): string;
export function validateCredentials(username: string, password: string): string | null;
export function shouldRequireSetupToken(env?: NodeJS.ProcessEnv): boolean;
export function isSecureCookieEnabled(env?: NodeJS.ProcessEnv): boolean;
export function verifySetupToken(
  submittedToken: FormDataEntryValue | string | null,
  env?: NodeJS.ProcessEnv,
): { ok: true } | { ok: false; reason: string };

export class FixedWindowRateLimiter {
  constructor(options: { maxAttempts: number; windowMs: number; now?: () => number });
  isLimited(key: string): boolean;
  recordFailure(key: string): void;
  clear(key: string): void;
}

export const loginRateLimiter: FixedWindowRateLimiter;
