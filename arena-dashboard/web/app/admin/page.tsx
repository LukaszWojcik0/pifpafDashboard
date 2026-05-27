import { getSession } from '../auth';
import { redirect } from 'next/navigation';
import db from '../db';
import Link from 'next/link';
import { revalidatePath } from 'next/cache';

export const dynamic = 'force-dynamic';

async function addSource(formData: FormData) {
  'use server';
  const session = await getSession();
  if (!session) throw new Error('Brak uprawnień');

  if (db) {
    const stmt = db.prepare(`
      INSERT INTO scraping_sources 
      (name, list_url, list_links_selector, title_selector, date_selector, time_selector, image_selector, tickets_regex, sold_out_regex)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    
    stmt.run(
      formData.get('name') as string,
      formData.get('list_url') as string,
      formData.get('list_links_selector') as string,
      formData.get('title_selector') as string,
      formData.get('date_selector') as string,
      formData.get('time_selector') as string,
      formData.get('image_selector') as string,
      formData.get('tickets_regex') as string,
      formData.get('sold_out_regex') as string
    );
    revalidatePath('/admin');
  }
}

export default async function AdminPage() {
  const session = await getSession();
  if (!session) {
    redirect('/login');
  }

  let sources: any[] = [];
  if (db) {
    sources = db.prepare('SELECT * FROM scraping_sources ORDER BY id DESC').all();
  }

  return (
    <main className="max-w-7xl mx-auto p-4 md:p-8 pt-8 md:pt-12">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Panel Administratora</h1>
        <Link href="/" className="text-blue-600 hover:text-blue-800 transition-colors">
          &larr; Powrót do Dashboardu
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 bg-white dark:bg-gray-800 p-6 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Dodaj nowe źródło wydarzeń</h2>
          <form action={addSource} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Nazwa (np. Miejscówka 2)</label>
              <input type="text" name="name" required className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Adres URL z listą wydarzeń</label>
              <input type="url" name="list_url" required placeholder="https://..." className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Selektor CSS dla linków do detali</label>
              <input type="text" name="list_links_selector" placeholder='np. a.event-card' className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Selektor CSS tytułu (na stronie detali)</label>
              <input type="text" name="title_selector" placeholder="np. h1.title" className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Selektor Daty</label>
                <input type="text" name="date_selector" placeholder='np. .event-date' className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Selektor Czasu</label>
                <input type="text" name="time_selector" placeholder='np. .event-time' className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Selektor Obrazka (img src lub meta content)</label>
              <input type="text" name="image_selector" placeholder='np. meta[property="og:image"]' className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Regex na ilość biletów w tekście</label>
              <input type="text" name="tickets_regex" placeholder='np. \((\d+)\s+dostępnych\)' className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
            </div>
            <button type="submit" className="w-full bg-blue-600 text-white font-medium py-2 rounded-lg hover:bg-blue-700 transition-colors">
              Zapisz źródło
            </button>
          </form>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Podłączone serwisy ({sources.length})</h2>
          {sources.map((src) => (
            <div key={src.id} className="bg-white dark:bg-gray-800 p-5 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-bold text-lg text-gray-900 dark:text-white">{src.name} {src.is_active ? '🟢' : '🔴'}</h3>
              </div>
              <a href={src.list_url} target="_blank" rel="noreferrer" className="text-blue-500 text-sm hover:underline break-all mb-4 block">
                {src.list_url}
              </a>
              <p className="text-xs text-gray-500 font-mono">Tytuł: {src.title_selector || 'Domyślny'}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}