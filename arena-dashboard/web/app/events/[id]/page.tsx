import { getEventById, getEventSnapshots } from '../../queries';
import EventAvailabilityChart from '../../EventAvailabilityChart';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getSession, logout } from '../../auth';
import StatusBadge from '../../StatusBadge';
import { updateMaxAvailable } from './actions';
import { Snapshot } from '../../types';
import { requireSiteAccess } from '../../siteAccess';

export const dynamic = 'force-dynamic';

export default async function EventPage({ params }: { params: Promise<{ id: string }> }) {
  await requireSiteAccess();
  const { id } = await params;
  const event = getEventById(id);
  if (!event) {
    console.warn(`Event details requested for missing event id: ${id}`);
    return notFound();
  }

  const snapshots = getEventSnapshots(id);
  const session = await getSession();

  const dailyMap = new Map<string, Snapshot>();
  snapshots.forEach((snapshot) => {
    if (snapshot.checked_at) {
      const dateStr = snapshot.checked_at.split('T')[0];
      dailyMap.set(dateStr, snapshot);
    }
  });
  const dailySnapshots = Array.from(dailyMap.values());

  const now = new Date();
  const startOfYesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  const recentSnapshots = snapshots.filter((snapshot) => new Date(snapshot.checked_at) >= startOfYesterday);

  return (
    <main className="max-w-5xl mx-auto p-4 md:p-8 pt-8 md:pt-12">
      <div className="flex justify-between items-center mb-6">
        <Link href="/" className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 font-medium inline-block transition-colors">
          &larr; Wroc do listy wydarzen
        </Link>

        {session ? (
          <div className="flex items-center gap-4">
            <Link href="/admin" className="text-sm font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 transition-colors">
              Panel Admina
            </Link>
            <form action={logout}>
              <button type="submit" className="text-sm px-3 py-1 bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50 rounded transition-colors">
                Wyloguj ({session})
              </button>
            </form>
          </div>
        ) : (
          <Link href="/login" className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
            Zaloguj sie
          </Link>
        )}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 mb-8 border border-gray-200 dark:border-gray-700">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-4">
          <div className="flex-1">
            <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-2">{event.title}</h1>
            <div className="flex flex-wrap items-center gap-2 text-gray-500 dark:text-gray-400">
              <span className="text-xs font-medium rounded-full bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 px-2 py-1">
                {event.source_name || 'Nieznane źródło'}
              </span>
              <span>{event.event_date} {event.event_time}</span>
            </div>
          </div>
          <div className="flex-shrink-0">
            <StatusBadge status={event.status} />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-6">
          <div>
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-2">Maksymalna liczba miejsc</h2>
            <div className="flex items-center gap-4">
              <p className="text-3xl font-bold text-gray-900 dark:text-white">{event.max_available ?? 'Brak danych'}</p>

              {session ? (
                <form action={updateMaxAvailable} className="flex items-center gap-2 ml-4">
                  <input type="hidden" name="id" value={event.id} />
                  <input
                    type="number"
                    name="max"
                    defaultValue={event.max_available ?? 0}
                    className="w-20 px-2 py-1 border rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white text-sm"
                    min="0"
                    max="100000"
                  />
                  <button type="submit" className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors">
                    Zapisz
                  </button>
                </form>
              ) : (
                <p className="text-xs text-gray-400 ml-4 italic">Zaloguj sie, aby edytowac.</p>
              )}
            </div>
            <p className="text-xs text-gray-400 mt-2">Mozesz recznie nadpisac liczbe biletow, jezeli wydarzenie zostalo pobrane po czesciowej wyprzedazy.</p>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-2">Ostatnia aktualizacja</h2>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">{new Date(event.last_seen).toLocaleString('pl-PL')}</p>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Historia dostepnosci biletow</h2>
        {snapshots.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
              <h3 className="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">Ogolny trend</h3>
              <EventAvailabilityChart snapshots={dailySnapshots} />
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 border border-gray-200 dark:border-gray-700 flex flex-col">
              <h3 className="text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200">Szczegolowe</h3>
              {recentSnapshots.length > 0 ? (
                <EventAvailabilityChart snapshots={recentSnapshots} />
              ) : (
                <div className="flex-1 flex min-h-[200px] items-center justify-center">
                  <p className="text-gray-500 dark:text-gray-400">Brak zmian w ostatnich dwoch dniach.</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          <p className="text-gray-500 dark:text-gray-400">Brak danych historycznych dla tego wydarzenia.</p>
        )}
      </div>
    </main>
  );
}
