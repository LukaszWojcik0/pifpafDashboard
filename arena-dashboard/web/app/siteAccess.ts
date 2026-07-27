'use server';

import crypto from 'crypto';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { revalidatePath } from 'next/cache';
import db from './db';
import { isSecureCookieEnabled, normalizeAuthInput } from './authPolicy.mjs';
import { getSession } from './auth';
import { hashPassword, randomSalt, safeCompareHex } from './passwordCrypto';

const COOKIE_NAME = 'site_access';
const MAX_AGE_SECONDS = 60 * 60 * 24 * 14;
const PASSWORD_HASH_KEY = 'site_access_password_hash';
const PASSWORD_SALT_KEY = 'site_access_password_salt';

type PasswordRecord = {
  hash: string;
  salt: string;
  source: 'site' | 'admin';
};

function statusValue(key: string): string | null {
  if (!db) return null;
  const row = db.prepare('SELECT value FROM system_status WHERE key = ?').get(key) as { value: string } | undefined;
  return row?.value ?? null;
}

function setStatusValue(key: string, value: string) {
  if (!db) throw new Error('Brak bazy danych');
  db.prepare(`
    INSERT INTO system_status (key, value, updated_at)
    VALUES (?, ?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
  `).run(key, value, new Date().toISOString());
}

function getPasswordRecord(): PasswordRecord | null {
  if (!db) return null;
  const siteHash = statusValue(PASSWORD_HASH_KEY);
  const siteSalt = statusValue(PASSWORD_SALT_KEY);
  if (siteHash && siteSalt) return { hash: siteHash, salt: siteSalt, source: 'site' };

  const admin = db
    .prepare('SELECT password_hash, salt FROM users ORDER BY created_at ASC, username ASC LIMIT 1')
    .get() as { password_hash: string; salt: string } | undefined;
  if (!admin) return null;
  return { hash: admin.password_hash, salt: admin.salt, source: 'admin' };
}

async function verifyAccessPassword(password: string): Promise<boolean> {
  const record = getPasswordRecord();
  if (!record) return false;
  const hash = await hashPassword(password, record.salt);
  return safeCompareHex(hash, record.hash);
}

function signAccessCookie(expiresAt: number, record: PasswordRecord): string {
  const payload = `${expiresAt}.${record.source}`;
  const signature = crypto.createHmac('sha256', record.hash).update(payload).digest('hex');
  return `${payload}.${signature}`;
}

function verifyAccessCookie(value: string | undefined): boolean {
  if (!value) return false;
  const record = getPasswordRecord();
  if (!record) return false;
  const parts = value.split('.');
  if (parts.length !== 3) return false;
  const expiresAt = Number(parts[0]);
  if (!Number.isFinite(expiresAt) || expiresAt < Date.now()) return false;
  const expected = signAccessCookie(expiresAt, record);
  if (value.length !== expected.length) return false;
  return crypto.timingSafeEqual(Buffer.from(value), Buffer.from(expected));
}

export async function isSiteAccessConfigured(): Promise<boolean> {
  return Boolean(getPasswordRecord());
}

export async function hasSiteAccess(): Promise<boolean> {
  const cookieStore = await cookies();
  return verifyAccessCookie(cookieStore.get(COOKIE_NAME)?.value);
}

export async function requireSiteAccess() {
  if (await hasSiteAccess()) return;
  redirect('/access');
}

export async function unlockSite(formData: FormData) {
  const password = normalizeAuthInput(formData.get('password'));
  if (!password || !(await verifyAccessPassword(password))) {
    redirect('/access?error=Nieprawidlowe haslo');
  }

  const record = getPasswordRecord();
  if (!record) redirect('/setup');

  const cookieStore = await cookies();
  const expiresAt = Date.now() + MAX_AGE_SECONDS * 1000;
  cookieStore.set(COOKIE_NAME, signAccessCookie(expiresAt, record), {
    httpOnly: true,
    secure: isSecureCookieEnabled(),
    maxAge: MAX_AGE_SECONDS,
    path: '/',
    sameSite: 'lax',
  });

  redirect('/');
}

export async function changeSiteAccessPassword(formData: FormData) {
  const session = await getSession();
  if (!session) throw new Error('Brak uprawnien');

  const password = normalizeAuthInput(formData.get('site_password'));
  if (password.length < 8 || password.length > 128) {
    throw new Error('Haslo strony musi miec od 8 do 128 znakow.');
  }

  const salt = randomSalt();
  const hashed = await hashPassword(password, salt);
  setStatusValue(PASSWORD_SALT_KEY, salt);
  setStatusValue(PASSWORD_HASH_KEY, hashed);

  const cookieStore = await cookies();
  const expiresAt = Date.now() + MAX_AGE_SECONDS * 1000;
  cookieStore.set(COOKIE_NAME, signAccessCookie(expiresAt, { hash: hashed, salt, source: 'site' }), {
    httpOnly: true,
    secure: isSecureCookieEnabled(),
    maxAge: MAX_AGE_SECONDS,
    path: '/',
    sameSite: 'lax',
  });

  revalidatePath('/admin');
  redirect('/admin?accessPassword=changed');
}
