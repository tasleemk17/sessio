import type { Kind } from "./types";

/** Money is stored in paise. 0 reads as "Free". */
export const rupees = (paise: number): string => (paise === 0 ? "Free" : `₹${(paise / 100).toLocaleString("en-IN")}`);

/** For earnings and totals, where zero is an amount, not "free". */
export const amount = (paise: number): string => `₹${(paise / 100).toLocaleString("en-IN")}`;

export const KIND_LABEL: Record<Kind, string> = { call: "1:1 call", document: "Document", dm: "Priority DM" };

/** Times arrive in UTC and are shown in the viewer's own time zone. */
export const dateTime = (iso: string): string =>
  new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

export const timeOnly = (iso: string): string => new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

/** "2026-11-04" in the viewer's own time zone, used to group slots by the day the viewer sees. */
export const localDay = (iso: string): string => new Date(iso).toLocaleDateString("en-CA");

export const dayChip = (day: string): { weekday: string; date: string } => {
  const d = new Date(`${day}T12:00:00`);
  return { weekday: d.toLocaleDateString(undefined, { weekday: "short" }), date: d.toLocaleDateString(undefined, { day: "numeric", month: "short" }) };
};

export const fileSize = (bytes: number): string => (bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`);

/** Minutes from midnight <-> the "HH:MM" an <input type="time"> uses. */
export const toClock = (minutes: number): string => `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
export const fromClock = (clock: string): number => {
  const [h, m] = clock.split(":").map(Number);
  return h * 60 + m;
};

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
