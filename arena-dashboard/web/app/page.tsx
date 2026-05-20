import { getEvents } from './queries';
import EventsTable from './EventsTable';
import { getSession, logout } from './auth';
import Link from 'next/link';

export const dynamic = 'force-dynamic';

export default function Home() {
  const events = getEvents();
  const session = getSession();

  return (
    <main className="max-w-7xl mx-auto p-4 md:p-8 pt-8 md:pt-12">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white">Dashboard Wydarzeń</h1>
        {session ? (
          <form action={logout}>
            <button type="submit" className="text-sm px-3 py-1 bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50 rounded transition-colors">
              Wyloguj ({session})
            </button>
          </form>
        ) : (
          <Link href="/login" className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
            Panel Admina
          </Link>
        )}
      </div>
      <EventsTable initialEvents={events} />
    </main>
  );
}