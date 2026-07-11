import { ScraperStatus } from './types';

function formatDate(value: string | null): string {
  if (!value) return 'brak danych';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('pl-PL');
}

export default function ScraperStatusBanner({ status }: { status: ScraperStatus }) {
  const hasFailure = status.status === 'failed' || Boolean(status.lastErrorAt);
  if (!status.stale && !hasFailure) return null;

  const summary = status.summary;

  return (
    <section className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100">
      <div className="font-semibold">
        {status.stale ? 'Dane moga byc nieaktualne' : 'Ostatni run scrapera zakonczyl sie bledem'}
      </div>
      <div className="mt-1 grid gap-1 md:grid-cols-2">
        <p>Ostatni sukces: {formatDate(status.lastSuccessAt)}</p>
        <p>Ostatni koniec runu: {formatDate(status.lastFinishedAt)}</p>
        <p>Status: {status.status ?? 'brak danych'}</p>
        <p>Prog stale: {status.staleAfterMinutes} min</p>
        {typeof status.durationSeconds === 'number' && <p>Czas trwania: {status.durationSeconds.toFixed(1)} s</p>}
        {hasFailure && <p>Ostatni blad: {status.lastErrorReason ?? 'brak szczegolow'}</p>}
      </div>
      <div className="mt-2 text-xs">
        Znalezione: {summary.found ?? 0}, poprawne: {summary.valid ?? 0}, odrzucone: {summary.rejected ?? 0}, utworzone:{' '}
        {summary.created ?? 0}, zaktualizowane: {summary.updated ?? 0}
      </div>
    </section>
  );
}
