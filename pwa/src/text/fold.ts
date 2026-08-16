/** Sdílené skládání textu pro hledání (katalog i Poblíž). */

export const SEARCH_MIN_CHARS = 3;
export const SEARCH_DEBOUNCE_MS = 500;

export function fold(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase("cs");
}

/** Krátký rozepsaný text se ještě nepoužije jako hledání. */
export function appliedSearchQuery(raw: string): string {
  const trimmed = raw.trim();
  return trimmed.length >= SEARCH_MIN_CHARS ? trimmed : "";
}
