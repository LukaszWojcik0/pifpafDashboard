"use client";

import { EventSnapshot } from "../lib/types";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { formatDate } from "../lib/utils";

export function EventAvailabilityChart({ data }: { data: EventSnapshot[] }) {
  const chartData = data.map(snapshot => ({
    time: formatDate(snapshot.timestamp),
    available: snapshot.available_places
  }));

  if (chartData.length === 0) {
    return <div className="p-8 text-center text-gray-500">Brak danych historycznych</div>;
  }

  return (
    <div className="h-96 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis 
            dataKey="time" 
            tick={{ fill: 'currentColor', fontSize: 12 }} 
            tickFormatter={(val) => val.split(',')[0]} // Show just date for brevity
          />
          <YAxis tick={{ fill: 'currentColor' }} />
          <Tooltip 
            contentStyle={{ backgroundColor: 'var(--card)', color: 'var(--foreground)', border: '1px solid var(--border)' }}
          />
          <Line 
            type="stepAfter" 
            dataKey="available" 
            stroke="#3b82f6" 
            strokeWidth={2} 
            dot={false}
            name="Dostępne miejsca"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
