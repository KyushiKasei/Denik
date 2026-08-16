import "fake-indexeddb/auto";
import { afterEach, beforeEach } from "vitest";
import { db } from "../src/db";
import { clearExportReminderDismiss } from "../src/diary/reminder";

if (typeof globalThis.localStorage === "undefined") {
  const data = new Map<string, string>();
  globalThis.localStorage = {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => {
      data.set(key, String(value));
    },
    removeItem: (key: string) => {
      data.delete(key);
    },
    clear: () => {
      data.clear();
    },
    key: (index: number) => [...data.keys()][index] ?? null,
    get length() {
      return data.size;
    },
  } as Storage;
}

beforeEach(async () => {
  localStorage.clear();
  clearExportReminderDismiss();
  if (db.isOpen()) {
    db.close();
  }
  await db.delete();
  await db.open();
});

afterEach(async () => {
  if (db.isOpen()) {
    db.close();
  }
});
