export const THEME_STORAGE_KEY = "pamatky-theme";

export type ThemePreference = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

export const THEME_COLOR_LIGHT = "#3d5a40";
export const THEME_COLOR_DARK = "#1a1814";

export interface ThemeRoot {
  setAttribute(name: string, value: string): void;
  removeAttribute(name: string): void;
}

function storage(): Storage | null {
  try {
    if (typeof localStorage === "undefined") {
      return null;
    }
    return localStorage;
  } catch {
    return null;
  }
}

export function parseThemePreference(value: string | null | undefined): ThemePreference {
  if (value === "light" || value === "dark") {
    return value;
  }
  return "system";
}

export function loadThemePreference(): ThemePreference {
  return parseThemePreference(storage()?.getItem(THEME_STORAGE_KEY));
}

export function saveThemePreference(preference: ThemePreference): void {
  const store = storage();
  if (!store) {
    return;
  }
  if (preference === "system") {
    store.removeItem(THEME_STORAGE_KEY);
    return;
  }
  store.setItem(THEME_STORAGE_KEY, preference);
}

export function applyTheme(preference: ThemePreference, root?: ThemeRoot | null): void {
  const el =
    root ?? (typeof document !== "undefined" ? document.documentElement : null);
  if (!el) {
    return;
  }
  if (preference === "light" || preference === "dark") {
    el.setAttribute("data-theme", preference);
    return;
  }
  el.removeAttribute("data-theme");
}

export function resolvedTheme(preference: ThemePreference, prefersDark?: boolean): ResolvedTheme {
  if (preference === "light" || preference === "dark") {
    return preference;
  }
  if (typeof prefersDark === "boolean") {
    return prefersDark ? "dark" : "light";
  }
  if (typeof matchMedia === "function") {
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return "light";
}

export function themeColorFor(resolved: ResolvedTheme): string {
  return resolved === "dark" ? THEME_COLOR_DARK : THEME_COLOR_LIGHT;
}

export function syncDocumentChrome(resolved: ResolvedTheme, doc: Document = document): void {
  const themeColor = doc.querySelector('meta[name="theme-color"]');
  if (themeColor) {
    themeColor.setAttribute("content", themeColorFor(resolved));
  }
  const statusBar = doc.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
  if (statusBar) {
    statusBar.setAttribute("content", resolved === "dark" ? "black-translucent" : "default");
  }
}

export function persistAndApplyTheme(preference: ThemePreference, root?: ThemeRoot | null): void {
  saveThemePreference(preference);
  applyTheme(preference, root);
  if (typeof document !== "undefined") {
    syncDocumentChrome(resolvedTheme(preference));
  }
}

export function bootTheme(): void {
  const preference = loadThemePreference();
  applyTheme(preference);
  if (typeof document !== "undefined") {
    syncDocumentChrome(resolvedTheme(preference));
  }
  if (typeof matchMedia !== "function") {
    return;
  }
  const mq = matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", () => {
    if (loadThemePreference() === "system") {
      syncDocumentChrome(resolvedTheme("system"));
    }
  });
}
