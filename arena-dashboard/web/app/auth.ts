'use server';

import db from './db';
import crypto from 'crypto';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

export async function getSession(): Promise<string | null> {
  const cookieStore = cookies();
  const token = cookieStore.get('session_token')?.value;
  if (!token || !db) return null;
  try {
    const stmt = db.prepare("SELECT username FROM sessions WHERE token = ? AND expires_at > datetime('now')");
    const session = stmt.get(token) as { username: string } | undefined;
    return session ? session.username : null;
  } catch (e) {
    // Błąd może wystąpić, jeśli np. tabela sesji jeszcze nie istnieje
    console.error("Błąd podczas weryfikacji sesji:", e);
    return null;
  }
}

export async function setupUser(formData: FormData) {
  if (!db) throw new Error('Brak bazy danych');
  
  // Blokada: Rejestracja dostępna TYLKO jeśli nie ma żadnych użytkowników
  const count = (db.prepare('SELECT count(*) as c FROM users').get() as any).c;
  if (count > 0) {
    redirect(`/login?error=${encodeURIComponent('Administrator już istnieje')}`);
  }

  const username = formData.get('username') as string;
  const password = formData.get('password') as string;

  if (!username || username.length < 3 || !password || password.length < 6) {
    redirect(`/setup?error=${encodeURIComponent('Dane są zbyt krótkie (min. 3 znaki login, 6 hasło)')}`);
  }

  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.pbkdf2Sync(password, salt, 310000, 64, 'sha512').toString('hex');

  db.prepare('INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)').run(username, hash, salt);
  
  redirect(`/login?msg=${encodeURIComponent('Konto utworzone. Możesz się zalogować')}`);
}

export async function loginUser(formData: FormData) {
  if (!db) throw new Error('Brak bazy danych');

  const username = formData.get('username') as string;
  const password = formData.get('password') as string;

  const user = db.prepare('SELECT username, password_hash, salt FROM users WHERE username = ?').get(username) as any;
  if (!user) redirect(`/login?error=${encodeURIComponent('Nieprawidłowy login lub hasło')}`);

  const hash = crypto.pbkdf2Sync(password, user.salt, 310000, 64, 'sha512').toString('hex');
  if (hash !== user.password_hash) redirect(`/login?error=${encodeURIComponent('Nieprawidłowy login lub hasło')}`);

  const token = crypto.randomBytes(32).toString('hex');
  // Token ważny 7 dni
  db.prepare("INSERT INTO sessions (token, username, expires_at) VALUES (?, ?, datetime('now', '+7 days'))").run(token, username);

  cookies().set('session_token', token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    maxAge: 60 * 60 * 24 * 7, // 7 days
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