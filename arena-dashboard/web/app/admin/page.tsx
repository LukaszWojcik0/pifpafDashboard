import { getEvents } from '../queries';
import db from '../db';
import { revalidatePath } from 'next/cache';
import Link from 'next/link';

export const dynamic = 'force-dynamic';

async function deleteEvent(formData: FormData) {
  'use server';
  const id = formData.get('id') as string;
  
  if (id && db) {
    // Kaskadowe usunięcie - najpierw historia, potem samo wydarzenie
    db.prepare('DELETE FROM snapshots WHERE event_id = ?').run(id);
    db.prepare('DELETE FROM events WHERE id = ?').run(id);
    
    // Wymuszenie odświeżenia obu stron aby nie pokazywały ujęć ze zbuforowanego cache'a
    revalidatePath('/admin');
    revalidatePath('/');
  }
}

export default async function AdminPage() {
  const events = getEvents();

  return (
    <main className="max-w-5xl mx-auto p-4 md:p-8 pt-8 md:pt-12">
      <Link href="/" className="text-blue-600 hover:text-blue-800 dark:text-blue-400 font-medium mb-6 inline-block">
        &larr; Wróć do dashboardu
      </Link>
      
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">Panel Administratora</h1>
      
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-200 dark:border-gray-700">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b dark:border-gray-700">
                <th className="py-3 px-2 font-semibold text-gray-700 dark:text-gray-300">ID</th>
                <th className="py-3 px-2 font-semibold text-gray-700 dark:text-gray-300">Tytuł / Nazwa</th>
                <th className="py-3 px-2 font-semibold text-red-600 dark:text-red-400">Akcja nieodwracalna</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {events.map((event) => (
                <tr key={event.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="py-3 px-2 text-sm text-gray-500">{event.id}</td>
                  <td className="py-3 px-2 font-medium">{event.title || 'Brak tytułu'}</td>
                  <td className="py-3 px-2">
                    <form action={deleteEvent}>
                      <input type="hidden" name="id" value={event.id} />
                      <button type="submit" className="bg-red-600 text-white px-4 py-1.5 rounded-md hover:bg-red-700 text-sm shadow-sm transition-colors">
                        Usuń wpis
                      </button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}