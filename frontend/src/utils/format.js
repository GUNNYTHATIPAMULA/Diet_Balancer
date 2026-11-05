/** Local calendar date as YYYY-MM-DD (not UTC — "today" means the user's today). */
export function todayISO(date = new Date()) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function parseISODate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function shiftDate(iso, days) {
  const d = parseISODate(iso);
  d.setDate(d.getDate() + days);
  return todayISO(d);
}

export function formatDay(iso, opts = { weekday: "long", day: "numeric", month: "long" }) {
  return parseISODate(iso).toLocaleDateString(undefined, opts);
}

export function shortDay(iso) {
  return parseISODate(iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric" });
}

export const kcal = (v) => `${Math.round(Number(v) || 0).toLocaleString()}`;
export const grams = (v, digits = 0) => `${(Number(v) || 0).toFixed(digits)} g`;
export const g1 = (v) => (v == null ? "—" : `${Number(v).toFixed(1)} g`);

export function relativeTime(isoDateTime) {
  if (!isoDateTime) return "never";
  const seconds = Math.round((Date.now() - new Date(isoDateTime).getTime()) / 1000);
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds} s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return new Date(isoDateTime).toLocaleString();
}

export function greeting(date = new Date()) {
  const h = date.getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export function newIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 12)}`;
}

export function firstName(fullName = "") {
  return fullName.trim().split(/\s+/)[0] || "there";
}
