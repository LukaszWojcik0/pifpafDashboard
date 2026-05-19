import { getEventById, getEventSnapshots } from '../../queries';
import EventAvailabilityChart from '../../EventAvailabilityChart';
import StatusBadge from '../../StatusBadge';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import db from '../../db';
import { revalidatePath } from 'next/cache';

export const dynamic = 'force-dynamic';

async function updateMaxAvailable(formData: FormData) {
  'use server';
  const id = formData.get('id') as string;
  const newMax = parseInt(formData.get('max') as string, 10);
  
  if (id && !isNaN(newMax) && db) {
    db.prepare('UPDATE events SET max_available = ? WHERE id = ?').run(newMax, id);
    revalidatePath(`/events/${id}`);
    revalidatePath(`/`);
  }
}

export default async function EventPage({ params }: { params: { id: string } }) {
  const id = params.id;
  if (!id) return notFound();

  const event = getEventById(id);
  if (!event) return notFound();

  const snapshots = getEventSnapshots(id);

  return (
    <main className="max-w-5xl mx-auto p-4 md:p-8 pt-8 md:pt-12">
      <Link href="/" className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 font-medium mb-6 inline-block transition-colors">
        &larr; Wróć do listy wydarzeń
      </Link>
      
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 mb-8 border border-gray-200 dark:border-gray-700">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-white mb-2">{event.title || 'Wydarzenie bez tytułu'}</h1>
            <p className="text-gray-600 dark:text-gray-400 text-lg">
              Data: <span className="font-semibold text-gray-800 dark:text-gray-200">{event.event_date}</span>
            </p>
            {event.link && (
              <a href={event.link} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-blue-500 hover:text-blue-600 dark:hover:text-blue-400 mt-3 inline-flex items-center gap-1 transition-colors">
                Otwórz stronę produktu &#8599;
              </a>
            )}
          </div>
          <div className="flex flex-col items-start md:items-end gap-3">
            <StatusBadge status={event.status} />
            <span className="text-xs text-gray-500 dark:text-gray-400">Ostatnia zmiana: {new Date(event.last_seen).toLocaleString('pl-PL')}</span>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
          <div className="bg-gray-50 dark:bg-gray-900/50 p-5 rounded-xl border border-gray-100 dark:border-gray-700">
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Początkowa / Maksymalna pula miejsc</p>
            <div className="flex items-center gap-4">
              <p className="text-3xl font-bold text-gray-900 dark:text-white">{event.max_available ?? 'Brak danych'}</p>
              
              <form action={updateMaxAvailable} className="flex items-center gap-2 ml-4">
                <input type="hidden" name="id" value={event.id} />
                <input 
                  type="number" 
                  name="max" 
                  defaultValue={event.max_available ?? 0}
                  className="w-20 px-2 py-1 border rounded dark:bg-gray-700 dark:border-gray-600 text-sm"
                  min="1"
                />
                <button type="submit" className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors">
                  Zapisz
                </button>
              </form>
            </div>
            <p className="text-xs text-gray-400 mt-2">Możesz ręcznie nadpisać ilość biletów, jeśli wydarzenie zostało pobrane po częściowej wyprzedaży.</p>
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Wykres dostępności biletów w czasie</h2>
        {snapshots.length > 0 ? <EventAvailabilityChart snapshots={snapshots} /> : <p className="text-gray-500 mt-4">Brak zapisanej historii dla tego wydarzenia.</p>}
      </div>
    </main>
  );
}