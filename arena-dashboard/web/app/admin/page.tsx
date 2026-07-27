import { getSession } from '../auth';
import { redirect } from 'next/navigation';
import db from '../db';
import Link from 'next/link';
import { revalidatePath } from 'next/cache';
import { getAdminEvents } from '../queries';
import { eventVisibilityLabel } from '../eventVisibility.mjs';
import SourceForm from '../../components/SourceForm';
import { changeSiteAccessPassword, requireSiteAccess } from '../siteAccess';

export const dynamic = 'force-dynamic';

async function addSource(formData: FormData) {
  'use server';
  const session = await getSession();
  if (!session) throw new Error('Brak uprawnien');

  const preset = formData.get('preset') as string;
  let list_url = formData.get('list_url') as string;
  let is_api = parseInt((formData.get('is_api') as string) || '0', 10);
  let list_links_selector = formData.get('list_links_selector') as string;
  let title_selector = formData.get('title_selector') as string;
  let date_selector = formData.get('date_selector') as string;
  let time_selector = formData.get('time_selector') as string;
  let image_selector = formData.get('image_selector') as string;
  let tickets_regex = formData.get('tickets_regex') as string;
  let sold_out_regex = formData.get('sold_out_regex') as string;
  let request_headers = formData.get('request_headers') as string;

  if (preset === 'playair') {
    const playairUrl = formData.get('playair_url') as string;
    let arenaId = '';
    const match = playairUrl.match(/arenaIds=([a-z0-9]+)/i);
    if (match) arenaId = match[1];
    else if (playairUrl.length === 32 && !playairUrl.includes('/')) arenaId = playairUrl;

    if (!arenaId) throw new Error('Nie znaleziono ID areny PlayAir w podanym linku');

    list_url = `https://api.playair.pro/api/event?arenaIds=${arenaId}&page=0&size=50&sort=startDate&startDate={TODAY}`;
    is_api = 1;
    list_links_selector = 'content';
    title_selector = 'name';
    date_selector = 'startDate';
    time_selector = 'startDate';
    image_selector = 'pictureId';
    tickets_regex = '';
    sold_out_regex = 'id';
  }

  if (db) {
    const stmt = db.prepare(`
      INSERT INTO scraping_sources
      (name, list_url, list_links_selector, title_selector, date_selector, time_selector, image_selector, tickets_regex, sold_out_regex, ntfy_url, ntfy_template, is_api, request_headers)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      formData.get('name') as string,
      list_url,
      list_links_selector,
      title_selector,
      date_selector,
      time_selector,
      image_selector,
      tickets_regex,
      sold_out_regex,
      formData.get('ntfy_url') as string,
      formData.get('ntfy_template') as string,
      is_api,
      request_headers,
    );
    revalidatePath('/admin');
  }
}

async function deleteEvent(formData: FormData) {
  'use server';
  const session = await getSession();
  if (!session) throw new Error('Brak uprawnien');

  const id = formData.get('id');
  if (db && id) {
    db.prepare('DELETE FROM events WHERE id = ?').run(id);
    revalidatePath('/admin');
  }
}

async function deleteSource(formData: FormData) {
  'use server';
  const session = await getSession();
  if (!session) throw new Error('Brak uprawnien');

  const id = formData.get('id');
  if (db && id) {
    db.prepare('DELETE FROM scraping_sources WHERE id = ?').run(id);
    revalidatePath('/admin');
  }
}

export default async function AdminPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  await requireSiteAccess();
  const session = await getSession();
  if (!session) redirect('/login');

  const resolvedSearchParams = await searchParams;
  const currentTab = resolvedSearchParams.tab === 'events' ? 'events' : 'sources';

  let sources: any[] = [];
  let events: any[] = [];
  if (db) {
    if (currentTab === 'sources') {
      sources = db.prepare('SELECT * FROM scraping_sources ORDER BY id DESC').all();
    } else {
      events = getAdminEvents();
    }
  }

  return (
    <main className="max-w-7xl mx-auto p-4 md:p-8 pt-8 md:pt-12">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Panel administratora</h1>
        <Link href="/" className="text-blue-600 hover:text-blue-800 transition-colors">
          &larr; Powrot do dashboardu
        </Link>
      </div>

      <div className="flex space-x-4 border-b border-gray-200 dark:border-gray-700 mb-8">
        <Link
          href="?tab=sources"
          className={`pb-3 px-2 text-sm font-medium border-b-2 transition-colors ${currentTab === 'sources' ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}`}
        >
          Zrodla scrapingu
        </Link>
        <Link
          href="?tab=events"
          className={`pb-3 px-2 text-sm font-medium border-b-2 transition-colors ${currentTab === 'events' ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'}`}
        >
          Zarzadzanie wydarzeniami
        </Link>
      </div>

      {currentTab === 'sources' && (
        <div className="space-y-8">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold mb-2 text-gray-900 dark:text-white">Haslo wejscia na dashboard</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              To haslo jest wymagane przed wejsciem na publiczna czesc strony. Sesja trwa 14 dni.
            </p>
            {resolvedSearchParams.accessPassword === 'changed' && (
              <p className="text-sm text-green-600 dark:text-green-400 mb-4">Haslo strony zostalo zmienione.</p>
            )}
            <form action={changeSiteAccessPassword} className="flex flex-col sm:flex-row gap-3">
              <input
                type="password"
                name="site_password"
                minLength={8}
                maxLength={128}
                required
                placeholder="Nowe haslo strony"
                className="w-full sm:max-w-sm px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
              />
              <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium">
                Zapisz haslo
              </button>
            </form>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1 bg-white dark:bg-gray-800 p-6 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Dodaj nowe zrodlo wydarzen</h2>
              <SourceForm action={addSource} />
            </div>

            <div className="lg:col-span-2 space-y-4">
              <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Podlaczone serwisy ({sources.length})</h2>
              {sources.map((src) => (
                <div key={src.id} className="bg-white dark:bg-gray-800 p-5 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 relative">
                  <form action={deleteSource} className="absolute top-5 right-5">
                    <input type="hidden" name="id" value={src.id} />
                    <button type="submit" className="text-red-500 hover:text-red-700 text-sm font-medium p-1">Usun</button>
                  </form>
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="font-bold text-lg text-gray-900 dark:text-white">
                      {src.name} {src.is_active ? 'aktywny' : 'wylaczony'} {src.is_api === 1 ? 'API' : 'HTML'}
                    </h3>
                  </div>
                  <a href={src.list_url} target="_blank" rel="noreferrer" className="text-blue-500 text-sm hover:underline break-all mb-4 block pr-12">
                    {src.list_url}
                  </a>
                  <p className="text-xs text-gray-500 font-mono">Tytul: {src.title_selector || 'Domyslny'}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {currentTab === 'events' && (
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="p-6 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Zapisane wydarzenia</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Wydarzenia niepewne i archiwalne sa ukryte na stronie glownej, ale widoczne tutaj do kontroli albo usuniecia.
            </p>
          </div>
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {events.map((evt) => (
              <div key={evt.id} className="p-4 sm:p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                <div className="overflow-hidden w-full">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-medium text-gray-900 dark:text-white truncate">{evt.title || 'Brak tytulu'}</h3>
                    <span className={`text-xs rounded-full px-2 py-1 ${
                      evt.visibility === 'public'
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                        : evt.visibility === 'past'
                          ? 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200'
                          : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                    }`}>
                      {eventVisibilityLabel(evt.visibility)}
                    </span>
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400 mt-1 flex flex-col sm:flex-row sm:gap-4">
                    <span>Zrodlo: {evt.source_name || 'Nieznane'}</span>
                    <span>Data: {evt.event_date || 'Brak'}</span>
                    <span>Status: {evt.status || 'Brak'}</span>
                    <span>Miejsca: {evt.current_available ?? '?'}/{evt.max_available ?? '?'}</span>
                    <a href={evt.link} target="_blank" rel="noreferrer" className="text-blue-500 hover:underline truncate block max-w-full">
                      {evt.link}
                    </a>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">{evt.visibility_reason}</p>
                </div>
                <form action={deleteEvent}>
                  <input type="hidden" name="id" value={evt.id} />
                  <button type="submit" className="px-4 py-2 bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors font-medium text-sm whitespace-nowrap">
                    Usun
                  </button>
                </form>
              </div>
            ))}
            {events.length === 0 && (
              <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                Brak wydarzen w bazie danych.
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
