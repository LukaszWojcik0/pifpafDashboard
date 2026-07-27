/**
 * @param {number | null | undefined} maxAvailable
 * @param {Array<number | null | undefined>} availabilityHistory
 * @param {number | null | undefined} [currentAvailable]
 * @returns {number | null}
 */
export function calculateCumulativePlayers(maxAvailable, availabilityHistory, currentAvailable = null) {
  if (maxAvailable === null || maxAvailable === undefined) return null;
  const max = Number(maxAvailable);
  if (!Number.isFinite(max) || max < 0) return null;

  const history = Array.isArray(availabilityHistory) ? availabilityHistory : [];
  if (history.length === 0) {
    if (currentAvailable === null || currentAvailable === undefined) return null;
    const current = Number(currentAvailable);
    if (!Number.isFinite(current) || current < 0 || current > max) return null;
    return Math.max(0, Math.trunc(max) - Math.trunc(current));
  }

  let players = 0;
  let previousAvailable = Math.trunc(max);
  for (const item of history) {
    if (item === null || item === undefined) continue;
    const available = Number(item);
    if (!Number.isFinite(available) || available < 0) continue;
    const normalizedAvailable = Math.trunc(available);
    if (normalizedAvailable < previousAvailable) {
      players += previousAvailable - normalizedAvailable;
    }
    previousAvailable = normalizedAvailable;
  }

  return Math.max(0, players);
}
