import { cn } from './utils';

const LABELS: Record<string, string> = {
  available: 'Bilety dostepne',
  sold_out: 'Wyprzedane',
  unknown: 'Nieznany',
};

export default function StatusBadge({ status }: { status: string }) {
  if (!status) return null;

  const canonical = status.toLowerCase();
  const isAvailable = canonical === 'available' || canonical.includes('dost');
  const isSoldOut = canonical === 'sold_out' || canonical.includes('wyprzed');
  const isUnknown = canonical === 'unknown' || canonical.includes('niezn');

  return (
    <span
      className={cn(
        'px-2.5 py-1 rounded-full text-xs font-medium border whitespace-nowrap',
        isAvailable
          ? 'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800'
          : isSoldOut
            ? 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800'
            : isUnknown
              ? 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800'
              : 'bg-gray-100 text-gray-800 border-gray-200 dark:bg-gray-800/50 dark:text-gray-300 dark:border-gray-700',
      )}
    >
      {LABELS[canonical] ?? status}
    </span>
  );
}
