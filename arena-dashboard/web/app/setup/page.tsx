import { setupUser } from '../auth';
import db from '../db';
import { redirect } from 'next/navigation';

export default function SetupPage({ searchParams }: { searchParams: { error?: string } }) {
  if (db) {
    // Jeśli jakikolwiek użytkownik istnieje, zablokuj dostęp do setupu
    try {
      const count = (db.prepare('SELECT count(*) as c FROM users').get() as any).c;
      if (count > 0) {
        redirect('/login');
      }
    } catch (e) {
      // Tabela może jeszcze nie istnieć, ignorujemy błąd
    }
  }

  return (
    <div className="max-w-md mx-auto mt-20 p-6 bg-white dark:bg-gray-800 rounded-xl shadow-md border border-gray-200 dark:border-gray-700">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Pierwsza konfiguracja</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-6">Utwórz konto administratora. Ta strona zniknie po rejestracji pierwszego użytkownika.</p>
      
      {searchParams.error && (
        <div className="mb-4 p-3 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 rounded-lg text-sm">
          {searchParams.error}
        </div>
      )}

      <form action={setupUser} className="flex flex-col gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Nazwa użytkownika</label>
          <input type="text" name="username" required minLength={3} className="w-full px-4 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Hasło</label>
          <input type="password" name="password" required minLength={6} className="w-full px-4 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
        </div>
        <button type="submit" className="w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">Utwórz konto</button>
      </form>
    </div>
  );
}
