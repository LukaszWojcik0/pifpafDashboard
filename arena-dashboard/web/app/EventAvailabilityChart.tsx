"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';
import { Snapshot } from './types';
import { format } from 'date-fns';
import { pl } from 'date-fns/locale';

export default function EventAvailabilityChart({ snapshots }: { snapshots: Snapshot[] }) {
  const data = snapshots.map(s => ({
    ...s,
    formattedDate: format(new Date(s.checked_at), 'dd MMM HH:mm', { locale: pl })
  }));

  return (
    <div className="h-[400px] w-full mt-4">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
          <XAxis dataKey="formattedDate" stroke="#9CA3AF" fontSize={12} tickMargin={10} />
          <YAxis stroke="#9CA3AF" fontSize={12} allowDecimals={false} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1F2937', borderColor: '#374151', color: '#F3F4F6', borderRadius: '8px' }}
            itemStyle={{ color: '#60A5FA', fontWeight: 600 }}
          />
          <Line type="stepAfter" dataKey="available" name="Dostępne bilety" stroke="#3B82F6" strokeWidth={3} dot={{ r: 4, fill: '#3B82F6', strokeWidth: 0 }} activeDot={{ r: 6 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}