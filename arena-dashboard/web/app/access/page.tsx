import { redirect } from 'next/navigation';
import { hasSiteAccess, isSiteAccessConfigured, unlockSite } from '../siteAccess';

export const dynamic = 'force-dynamic';

export default async function AccessPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  if (await hasSiteAccess()) redirect('/');
  if (!(await isSiteAccessConfigured())) redirect('/setup');
  const params = await searchParams;

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 p-4">
      <div className="w-full max-w-sm bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Dostep do dashboardu</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
          Wpisz haslo strony. Sesja zostanie zapamietana na 14 dni.
        </p>
        {params.error && (
          <p className="mb-4 text-sm text-red-600 dark:text-red-400">{params.error}</p>
        )}
        <form action={unlockSite} className="space-y-4">
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="Haslo"
            required
          />
          <button type="submit" className="w-full px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium">
            Wejdz
          </button>
        </form>
      </div>
    </main>
  );
}
