"use client";

import Link from "next/link";
import { Event } from "../lib/types";
import { StatusBadge } from "./StatusBadge";
import { useState } from "react";
import { formatDate } from "../lib/utils";

export function EventsTable({ initialEvents }: { initialEvents: Event[] }) {
  const [events, setEvents] = useState(initialEvents);
  const [sortField, setSortField] = useState<keyof Event>("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  const handleSort = (field: keyof Event) => {
    const isAsc = sortField === field && sortOrder === "asc";
    setSortOrder(isAsc ? "desc" : "asc");
    setSortField(field);

    const sorted = [...events].sort((a, b) => {
      const aVal = a[field] ?? "";
      const bVal = b[field] ?? "";
      if (aVal < bVal) return isAsc ? -1 : 1;
      if (aVal > bVal) return isAsc ? 1 : -1;
      return 0;
    });
    setEvents(sorted);
  };

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
          <tr>
            <th onClick={() => handleSort("title")} className="px-6 py-3 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700">Wydarzenie ↕</th>
            <th onClick={() => handleSort("date_info")} className="px-6 py-3 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700">Data ↕</th>
            <th onClick={() => handleSort("current_available")} className="px-6 py-3 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700">Aktualnie miejsc ↕</th>
            <th className="px-6 py-3">Status</th>
            <th className="px-6 py-3">Akcje</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id} className="border-b border-border hover:bg-gray-50 dark:hover:bg-gray-800/50">
              <td className="px-6 py-4 font-medium text-foreground">
                <Link href={`/events/${event.id}`} className="hover:underline">
                  {event.title}
                </Link>
              </td>
              <td className="px-6 py-4">{event.date_info}</td>
              <td className="px-6 py-4">{event.current_available ?? 0} / {event.max_available}</td>
              <td className="px-6 py-4">
                <StatusBadge available={event.current_available ?? 0} max={event.max_available} />
              </td>
              <td className="px-6 py-4">
                 <Link href={`/events/${event.id}`} className="text-blue-600 dark:text-blue-400 hover:underline">
                  Szczegóły
                </Link>
              </td>
            </tr>
          ))}
          {events.length === 0 && (
             <tr>
               <td colSpan={5} className="px-6 py-8 text-center text-gray-500">Brak danych o wydarzeniach</td>
             </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
