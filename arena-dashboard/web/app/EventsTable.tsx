"use client";

import { useState } from 'react';
import { Event } from './types';
import Link from 'next/link';
import StatusBadge from './StatusBadge';

export default function EventsTable({ initialEvents }: { initialEvents: Event[] }) {
  const [search, setSearch] = useState('');
  
  const filteredEvents = initialEvents.filter(e => 
    (e.title || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="w-full">
      <div className="mb-6">
        <input
          type="text"
          placeholder="Szukaj wydarzenia..."
          className="w-full md:w-1/3 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
        <table className="w-full text-left border-collapse bg-white dark:bg-gray-800">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-900/50 border-b border-gray-200 dark:border-gray-700">
              <th className="px-6 py-4 font-semibold text-gray-700 dark:text-gray-300">Tytuł</th>
              <th className="px-6 py-4 font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap">Data / Czas</th>
              <th className="px-6 py-4 font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap">Miejsca</th>
              <th className="px-6 py-4 font-semibold text-gray-700 dark:text-gray-300">Status</th>
              <th className="px-6 py-4 font-semibold text-gray-700 dark:text-gray-300">Szczegóły</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {filteredEvents.map((event) => (
              <tr key={event.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                <td className="px-6 py-4 font-medium text-gray-900 dark:text-gray-100">{event.title || 'Brak tytułu'}</td>
                <td className="px-6 py-4 text-gray-600 dark:text-gray-400 whitespace-nowrap">{event.event_date} {event.event_time}</td>
                <td className="px-6 py-4 text-gray-900 dark:text-gray-100 font-semibold">{event.max_available ?? '-'}</td>
                <td className="px-6 py-4"><StatusBadge status={event.status} /></td>
                <td className="px-6 py-4">
                  <Link href={`/events/${event.id}`} className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 font-medium whitespace-nowrap">
                    Otwórz &rarr;
                  </Link>
                </td>
              </tr>
            ))}
            {filteredEvents.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-500">Brak wydarzeń spełniających kryteria.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}