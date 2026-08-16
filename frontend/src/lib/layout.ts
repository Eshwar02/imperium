// Pure helpers for resizable workbench regions — persistence + clamping kept out
// of React so they can be unit-tested (see layout.test.ts).

/** Clamp a pixel size into [min, max]; non-finite input falls back to min. */
export function clampSize(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, Math.round(value)));
}

const PREFIX = "imperium.layout.";

/** Read a persisted size, clamped; returns `fallback` when absent/invalid. */
export function loadSize(key: string, fallback: number, min: number, max: number): number {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    if (raw == null) return clampSize(fallback, min, max);
    const n = Number(raw);
    return Number.isFinite(n) ? clampSize(n, min, max) : clampSize(fallback, min, max);
  } catch {
    return clampSize(fallback, min, max);
  }
}

/** Persist a size (best-effort; storage may be unavailable). */
export function saveSize(key: string, value: number): void {
  try {
    localStorage.setItem(PREFIX + key, String(Math.round(value)));
  } catch {
    /* ignore quota / disabled storage */
  }
}
