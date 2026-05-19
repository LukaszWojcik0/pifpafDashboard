import { getEvents } from './queries';
import EventsTable from './EventsTable';

// Zawsze pobieraj aktualne statystyki prosto z bazy SQLite w momencie requestu
export const dynamic = 'force-dynamic';

export default function Home() {
  const events = getEvents();

  return (
    <main className="max-w-7xl mx-auto p-4 md:p-8 pt-8 md:pt-12">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white">Dashboard ArenaWalki</h1>
        <a href="/admin" className="text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">
          Admin Panel
        </a>
      </div>
      <EventsTable initialEvents={events} />
    </main>
  );
}