import { getEventById, getEventSnapshots } from '../../queries';
import EventAvailabilityChart from '../../EventAvailabilityChart';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import db from '../../db';
import { revalidatePath } from 'next/cache';
import { getSession, logout } from '../../auth';
import StatusBadge from '../../StatusBadge';

export const dynamic = 'force-dynamic';

export async function updateMaxAvailable(formData: FormData) {
  'use server';
  const session = await getSession();
  if (!session) {
    throw new Error('Odmowa dostępu. Proszę się zalogować.');
  }

  const id = formData.get('id') as string;
  const newMaxStr = formData.get('max') as string;
  const newMax = parseInt(newMaxStr, 10);
  
  // Ekstremalnie ścisła walidacja
  if (!id || typeof id !== 'string' || isNaN(newMax) || newMax < 0 || newMax > 100000) {
    console.error("Nieprawidłowa wartość podana przez formularz.");
    return; 
  }

  if (db) {
    db.prepare('UPDATE events SET max_available = ? WHERE id = ?').run(newMax, id);
    revalidatePath(`/events/${id}`);
    revalidatePath(`/`);
  }
}

export default async function EventPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const event = getEventById(id);
  if (!event) return notFound();

  const snapshots = getEventSnapshots(id);
  const session = await getSession();

  return (
    <main className="max-w-5xl mx-auto p-4 md:p-8 pt-8 md:pt-12">
      <div className="flex justify-between items-center mb-6">
        <Link href="/" className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 font-medium inline-block transition-colors">
          &larr; Wróć do listy wydarzeń
        </Link>
        
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
      
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 mb-8 border border-gray-200 dark:border-gray-700">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-4">
          <div className="flex-1">
            <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white mb-2">{event.title}</h1>
            <p className="text-gray-500 dark:text-gray-400">{event.event_date} {event.event_time}</p>
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
                  />
                  <button type="submit" className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors">
                    Zapisz
                  </button>
                </form>
              ) : (
                <p className="text-xs text-gray-400 ml-4 italic">Zaloguj się, aby edytować.</p>
              )}
            </div>
            <p className="text-xs text-gray-400 mt-2">Możesz ręcznie nadpisać ilość biletów, jeśli wydarzenie zostało pobrane po częściowej wyprzedaży.</p>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-2">Ostatnia aktualizacja</h2>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">{new Date(event.last_seen).toLocaleString('pl-PL')}</p>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Historia dostępności biletów</h2>
        {snapshots.length > 0 ? (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
            <EventAvailabilityChart snapshots={snapshots} />
          </div>
        ) : (
          <p className="text-gray-500 dark:text-gray-400">Brak danych historycznych dla tego wydarzenia.</p>
        )}
      </div>
    </main>
  );
}