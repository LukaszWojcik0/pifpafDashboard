'use server';

import crypto from 'crypto';
import { promisify } from 'util';
import { cookies, headers } from 'next/headers';
import { redirect } from 'next/navigation';
import db from './db';
import {
  isSecureCookieEnabled,
  loginRateLimiter,
  normalizeAuthInput,
  validateCredentials,
  verifySetupToken,
} from './authPolicy.mjs';

const pbkdf2 = promisify(crypto.pbkdf2);

type UserRecord = {
  username: string;
  password_hash: string;
  salt: string;
};

function redirectWithError(path: string, message: string): never {
  redirect(`${path}?error=${encodeURIComponent(message)}`);
}

async function hashPassword(password: string, salt: string): Promise<string> {
  const derivedKey = await pbkdf2(password, salt, 310000, 64, 'sha512');
  return derivedKey.toString('hex');
}

function safeCompareHex(value: string, expected: string): boolean {
  const valueBuffer = Buffer.from(value, 'hex');
  const expectedBuffer = Buffer.from(expected, 'hex');
  return valueBuffer.length === expectedBuffer.length && crypto.timingSafeEqual(valueBuffer, expectedBuffer);
}

function clientAddress(): string {
  const requestHeaders = headers();
  return (
    requestHeaders.get('cf-connecting-ip') ||
    requestHeaders.get('x-real-ip') ||
    requestHeaders.get('x-forwarded-for')?.split(',')[0]?.trim() ||
    'unknown'
  );
}

function loginRateLimitKey(username: string): string {
  return `${username.toLowerCase()}:${clientAddress()}`;
}

export async function getSession(): Promise<string | null> {
  const cookieStore = cookies();
  const token = cookieStore.get('session_token')?.value;
  if (!token || !db) return null;

  try {
    const stmt = db.prepare("SELECT username FROM sessions WHERE token = ? AND expires_at > datetime('now')");
    const session = stmt.get(token) as { username: string } | undefined;
    return session ? session.username : null;
  } catch (error) {
    console.error('Blad podczas weryfikacji sesji:', error);
    return null;
  }
}

export async function setupUser(formData: FormData) {
  const database = db;
  if (!database) throw new Error('Brak bazy danych');

  const count = (database.prepare('SELECT count(*) as c FROM users').get() as { c: number }).c;
  if (count > 0) {
    redirect(`/login?error=${encodeURIComponent('Administrator juz istnieje')}`);
  }

  const username = normalizeAuthInput(formData.get('username'));
  const password = normalizeAuthInput(formData.get('password'));
  const validationError = validateCredentials(username, password);
  if (validationError) {
    redirectWithError('/setup', validationError);
  }

  const setupToken = verifySetupToken(formData.get('setup_token'));
  if (!setupToken.ok) {
    redirectWithError('/setup', setupToken.reason ?? 'Nieprawidlowy token pierwszej konfiguracji.');
  }

  const salt = crypto.randomBytes(16).toString('hex');
  const hash = await hashPassword(password, salt);

  const createFirstAdmin = database.transaction(() => {
    const currentCount = (database.prepare('SELECT count(*) as c FROM users').get() as { c: number }).c;
    if (currentCount > 0) return false;
    database.prepare('INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)').run(username, hash, salt);
    return true;
  });

  if (!createFirstAdmin()) {
    redirect(`/login?error=${encodeURIComponent('Administrator juz istnieje')}`);
  }

  redirect(`/login?msg=${encodeURIComponent('Konto utworzone. Mozesz sie zalogowac')}`);
}

export async function loginUser(formData: FormData) {
  const database = db;
  if (!database) throw new Error('Brak bazy danych');

  const username = normalizeAuthInput(formData.get('username'));
  const password = normalizeAuthInput(formData.get('password'));
  const validationError = validateCredentials(username, password);
  if (validationError) {
    redirectWithError('/login', 'Nieprawidlowy login lub haslo');
  }

  const rateLimitKey = loginRateLimitKey(username);
  if (loginRateLimiter.isLimited(rateLimitKey)) {
    redirectWithError('/login', 'Zbyt wiele nieudanych prob logowania. Sprobuj ponownie pozniej.');
  }

  const user = database.prepare('SELECT username, password_hash, salt FROM users WHERE username = ?').get(username) as UserRecord | undefined;
  if (!user) {
    loginRateLimiter.recordFailure(rateLimitKey);
    redirectWithError('/login', 'Nieprawidlowy login lub haslo');
  }

  const hash = await hashPassword(password, user.salt);
  if (!safeCompareHex(hash, user.password_hash)) {
    loginRateLimiter.recordFailure(rateLimitKey);
    redirectWithError('/login', 'Nieprawidlowy login lub haslo');
  }

  loginRateLimiter.clear(rateLimitKey);

  const token = crypto.randomBytes(32).toString('hex');
  database.prepare("INSERT INTO sessions (token, username, expires_at) VALUES (?, ?, datetime('now', '+7 days'))").run(token, username);

  cookies().set('session_token', token, {
    httpOnly: true,
    secure: isSecureCookieEnabled(),
    maxAge: 60 * 60 * 24 * 7,
    path: '/',
    sameSite: 'lax',
  });

  redirect('/');
}

export async function logout() {
  const token = cookies().get('session_token')?.value;
  if (token && db) db.prepare('DELETE FROM sessions WHERE token = ?').run(token);
  cookies().delete('session_token');
  redirect('/login');
}
