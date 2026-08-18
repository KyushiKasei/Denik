import { afterEach, expect, test } from "vitest";
import {
  THEME_COLOR_DARK,
  THEME_COLOR_LIGHT,
  THEME_STORAGE_KEY,
  applyTheme,
  loadThemePreference,
  parseThemePreference,
  persistAndApplyTheme,
  resolvedTheme,
  saveThemePreference,
  syncDocumentChrome,
  themeColorFor,
  type ThemeRoot,
} from "../src/theme";

function fakeRoot(): ThemeRoot & { attrs: Map<string, string> } {
  const attrs = new Map<string, string>();
  return {
    attrs,
    setAttribute(name: string, value: string) {
      attrs.set(name, value);
    },
    removeAttribute(name: string) {
      attrs.delete(name);
    },
  };
}

afterEach(() => {
  localStorage.removeItem(THEME_STORAGE_KEY);
});

test("parseThemePreference přijme jen light/dark, jinak system", () => {
  expect(parseThemePreference("light")).toBe("light");
  expect(parseThemePreference("dark")).toBe("dark");
  expect(parseThemePreference("system")).toBe("system");
  expect(parseThemePreference(null)).toBe("system");
  expect(parseThemePreference("")).toBe("system");
  expect(parseThemePreference("foo")).toBe("system");
});

test("save a load preference v localStorage", () => {
  expect(loadThemePreference()).toBe("system");
  saveThemePreference("dark");
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  expect(loadThemePreference()).toBe("dark");
  saveThemePreference("system");
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
  expect(loadThemePreference()).toBe("system");
});

test("applyTheme nastaví data-theme jen u light/dark", () => {
  const root = fakeRoot();
  applyTheme("dark", root);
  expect(root.attrs.get("data-theme")).toBe("dark");
  applyTheme("light", root);
  expect(root.attrs.get("data-theme")).toBe("light");
  applyTheme("system", root);
  expect(root.attrs.has("data-theme")).toBe(false);
});

test("resolvedTheme: system sleduje OS, light/dark jsou vynucené", () => {
  expect(resolvedTheme("system", true)).toBe("dark");
  expect(resolvedTheme("system", false)).toBe("light");
  expect(resolvedTheme("light", true)).toBe("light");
  expect(resolvedTheme("dark", false)).toBe("dark");
});

test("themeColorFor vrací barvu podle resolved tématu", () => {
  expect(themeColorFor("light")).toBe(THEME_COLOR_LIGHT);
  expect(themeColorFor("dark")).toBe(THEME_COLOR_DARK);
});

test("persistAndApplyTheme uloží a aplikuje", () => {
  const root = fakeRoot();
  persistAndApplyTheme("dark", root);
  expect(loadThemePreference()).toBe("dark");
  expect(root.attrs.get("data-theme")).toBe("dark");
  persistAndApplyTheme("system", root);
  expect(loadThemePreference()).toBe("system");
  expect(root.attrs.has("data-theme")).toBe(false);
});

test("syncDocumentChrome nastaví theme-color a status bar", () => {
  const doc = {
    querySelector(selector: string) {
      if (selector === 'meta[name="theme-color"]') {
        return themeColor;
      }
      if (selector === 'meta[name="apple-mobile-web-app-status-bar-style"]') {
        return statusBar;
      }
      return null;
    },
  } as unknown as Document;
  const themeColor = { content: "#3d5a40", setAttribute(name: string, value: string) {
    if (name === "content") this.content = value;
  } };
  const statusBar = { content: "default", setAttribute(name: string, value: string) {
    if (name === "content") this.content = value;
  } };

  syncDocumentChrome("dark", doc);
  expect(themeColor.content).toBe(THEME_COLOR_DARK);
  expect(statusBar.content).toBe("black-translucent");
  syncDocumentChrome("light", doc);
  expect(themeColor.content).toBe(THEME_COLOR_LIGHT);
  expect(statusBar.content).toBe("default");
});
