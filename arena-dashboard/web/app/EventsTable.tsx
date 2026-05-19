"use client";

import { useState } from "react";
import Link from "next/link";
import StatusBadge from "./StatusBadge";
import { Event } from "./types";

export default function EventsTable({
  initialEvents,
}: {
  initialEvents: Event[];
}) {
  const [search, setSearch] = useState("");

  const filteredEvents = initialEvents.filter((e) =>
    (e.title || "").toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="w-full">
      <div className="mb-8">
        <input
          type="text"
          placeholder="Szukaj wydarzenia..."
          className="w-full max-w-md px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none transition-shadow"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {filteredEvents.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {filteredEvents.map((event) => (
            <div
              key={event.id}
              className="bg-white dark:bg-gray-800 rounded-xl shadow-md border border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col transition-transform hover:scale-[1.02]"
            >
              <Link href={`/events/${event.id}`} className="block">
                <img
                  src={
                    event.image_url ||
                    `https://via.placeholder.com/400x225.png?text=${encodeURIComponent(event.title || "Brak obrazka")}`
                  }
                  alt={`Obraz wydarzenia ${event.title}`}
                  className="w-full h-48 object-cover"
                />
              </Link>
              <div className="p-5 flex flex-col flex-grow">
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">
                  {event.event_date} {event.event_time}
                </p>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3 flex-grow">
                  <Link
                    href={`/events/${event.id}`}
                    className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                  >
                    {event.title || "Brak tytułu"}
                  </Link>
                </h3>

                <div className="flex justify-between items-center gap-4 mt-4">
                  <StatusBadge status={event.status} />
                  <div className="text-right">
                    <p className="font-extrabold text-2xl text-gray-900 dark:text-white">
                      {event.current_available ?? "?"}
                      <span className="text-base font-medium text-gray-500 dark:text-gray-400">
                        /{event.max_available ?? "?"}
                      </span>
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 -mt-1">
                      miejsc
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-20 px-6 bg-gray-50 dark:bg-gray-800/50 rounded-xl">
          <h3 className="text-xl font-semibold text-gray-800 dark:text-gray-200">
            Brak wydarzeń
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mt-2">
            Nie znaleziono żadnych wydarzeń pasujących do Twojego wyszukiwania.
          </p>
        </div>
      )}
    </div>
  );
}
