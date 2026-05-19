import { cn } from './utils';

export default function StatusBadge({ status }: { status: string }) {
  if (!status) return null;

  const s = status.toLowerCase();
  const isAvailable = s.includes('dostępne');
  const isSoldOut = s.includes('wyprzedane');
  const isClosed = s.includes('zamknięta');

  return (
    <span
      className={cn(
        'px-2.5 py-1 rounded-full text-xs font-medium border whitespace-nowrap',
        isAvailable ? 'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800' :
        isSoldOut ? 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800' :
        isClosed ? 'bg-gray-100 text-gray-800 border-gray-200 dark:bg-gray-800/50 dark:text-gray-300 dark:border-gray-700' :
        'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800'
      )}
    >
      {status}
    </span>
  );
}