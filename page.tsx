import { loginUser } from '../auth';
import db from '../db';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { SubmitButton } from './SubmitButton';

export default function LoginPage({ searchParams }: { searchParams: { error?: string, msg?: string } }) {
  if (db) {
    const count = (db.prepare('SELECT count(*) as c FROM users').get() as any).c;
    if (count === 0) {
      redirect('/setup'); // Skieruj na setup, jeśli baza jest pusta
    }
  }

  return (
    <div className="max-w-md mx-auto mt-20 p-6 bg-white dark:bg-gray-800 rounded-xl shadow-md border border-gray-200 dark:border-gray-700">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Logowanie do panelu</h1>
        <Link href="/" className="text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 transition-colors">Wróć do dashboardu</Link>
      </div>
      
      {searchParams.error && (
        <div className="mb-4 p-3 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 rounded-lg text-sm">
          {searchParams.error}
        </div>
      )}

      {searchParams.msg && (
        <div className="mb-4 p-3 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded-lg text-sm">
          {searchParams.msg}
        </div>
      )}

      <form action={loginUser} className="flex flex-col gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Nazwa użytkownika</label>
          <input type="text" name="username" required className="w-full px-4 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Hasło</label>
          <input type="password" name="password" required className="w-full px-4 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
        </div>
        <SubmitButton />
      </form>
    </div>
  );
}