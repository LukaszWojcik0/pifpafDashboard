import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string | null) {
  if (!dateString) return "N/A";
  try {
    return new Date(dateString).toLocaleString("pl-PL");
  } catch (e) {
    return dateString;
  }
}
