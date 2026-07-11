import { setupUser } from '../auth';
import { AUTH_LIMITS, shouldRequireSetupToken } from '../authPolicy.mjs';
import db from '../db';
import { redirect } from 'next/navigation';

export default function SetupPage({ searchParams }: { searchParams: { error?: string } }) {
  if (db) {
    try {
      const count = (db.prepare('SELECT count(*) as c FROM users').get() as { c: number }).c;
      if (count > 0) {
        redirect('/login');
      }
    } catch {
      // The users table can be absent before first database initialization.
    }
  }

  return (
    <div className="max-w-md mx-auto mt-20 p-6 bg-white dark:bg-gray-800 rounded-xl shadow-md border border-gray-200 dark:border-gray-700">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Pierwsza konfiguracja</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-6">Utworz konto administratora. Ta strona zniknie po rejestracji pierwszego uzytkownika.</p>

      {searchParams.error && (
        <div className="mb-4 p-3 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 rounded-lg text-sm">
          {searchParams.error}
        </div>
      )}

      <form action={setupUser} className="flex flex-col gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Nazwa uzytkownika</label>
          <input type="text" name="username" required minLength={AUTH_LIMITS.usernameMin} maxLength={AUTH_LIMITS.usernameMax} className="w-full px-4 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Haslo</label>
          <input type="password" name="password" required minLength={AUTH_LIMITS.passwordMin} maxLength={AUTH_LIMITS.passwordMax} className="w-full px-4 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
        </div>
        {shouldRequireSetupToken() && (
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Token pierwszej konfiguracji</label>
            <input type="password" name="setup_token" required maxLength={AUTH_LIMITS.setupTokenMax} className="w-full px-4 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
          </div>
        )}
        <button type="submit" className="w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">Utworz konto</button>
      </form>
    </div>
  );
}
