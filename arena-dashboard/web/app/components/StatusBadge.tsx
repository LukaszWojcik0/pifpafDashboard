import { cn } from "../lib/utils";

interface StatusBadgeProps {
  available: number;
  max: number;
}

export function StatusBadge({ available, max }: StatusBadgeProps) {
  let status = "ok";
  let label = "Dostępne";

  if (available === 0) {
    status = "empty";
    label = "Brak miejsc";
  } else if (available <= 5 || (max > 0 && available / max < 0.2)) {
    status = "low";
    label = "Mało miejsc";
  }

  return (
    <span
      className={cn(
        "px-2 py-1 text-xs font-semibold rounded-full",
        status === "ok" && "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100",
        status === "low" && "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100",
        status === "empty" && "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100"
      )}
    >
      {label}
    </span>
  );
}
