import { getEvents } from '../lib/queries';
import EventsTable from './EventsTable';

// Zawsze pobieraj aktualne statystyki prosto z bazy SQLite w momencie requestu
export const dynamic = 'force-dynamic';

export default function Home() {
  const events = getEvents();

  return (
    <main className="max-w-7xl mx-auto p-4 md:p-8 pt-8 md:pt-12">
      <h1 className="text-3xl md:text-4xl font-bold mb-8 text-gray-900 dark:text-white">Dashboard ArenaWalki</h1>
      <EventsTable initialEvents={events} />
    </main>
  );
}