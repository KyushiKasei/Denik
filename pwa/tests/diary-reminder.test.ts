import "fake-indexeddb/auto";
import { expect, test } from "vitest";
import { db } from "../src/db";
import {
  diaryExportReminder,
  dismissExportReminder,
  EXPORT_REMINDER_DAYS,
  EXPORT_REMINDER_DISMISS_KEY,
} from "../src/diary/reminder";
import type { StoredVisit } from "../src/catalog/types";

function visit(id: string, createdAt: string): StoredVisit {
  return {
    id,
    place_id: "0198f23a-5e5e-7b31-a8be-8c99507a2138",
    visited_at: "2026-08-09",
    rating: 5,
    people: [],
    note: null,
    created_at: createdAt,
    updated_at: createdAt,
    deleted_at: null,
  };
}

test("bez návštěv se připomínka neukáže", async () => {
  const info = await diaryExportReminder();
  expect(info.show).toBe(false);
});

test("5 nových návštěv bez exportu zapne připomínku", async () => {
  const now = new Date().toISOString();
  await db.visits.bulkPut([
    visit("0198f93b-618d-762f-a589-ccf375139dd1", now),
    visit("0198f93b-618d-762f-a589-ccf375139dd2", now),
    visit("0198f93b-618d-762f-a589-ccf375139dd3", now),
    visit("0198f93b-618d-762f-a589-ccf375139dd4", now),
    visit("0198f93b-618d-762f-a589-ccf375139dd5", now),
  ]);
  const info = await diaryExportReminder();
  expect(info.show).toBe(true);
  expect(info.neverExported).toBe(true);
  expect(info.newVisits).toBe(5);
});

test("mezery v created_at nepřekazí výpočet dnů", async () => {
  await db.visits.bulkPut([visit("0198f93b-618d-762f-a589-ccf375139de0", " 2026-01-01T12:00:00+02:00 ")]);
  const info = await diaryExportReminder();
  expect(info.show).toBe(true);
  expect(info.daysSinceExport).toBeGreaterThanOrEqual(EXPORT_REMINDER_DAYS);
});

test("odložení připomínky se uloží a schová banner", async () => {
  const now = new Date().toISOString();
  await db.visits.bulkPut([
    visit("0198f93b-618d-762f-a589-ccf375139dd1", now),
    visit("0198f93b-618d-762f-a589-ccf375139dd2", now),
    visit("0198f93b-618d-762f-a589-ccf375139dd3", now),
    visit("0198f93b-618d-762f-a589-ccf375139dd4", now),
    visit("0198f93b-618d-762f-a589-ccf375139dd5", now),
  ]);
  const before = await diaryExportReminder();
  expect(before.show).toBe(true);
  dismissExportReminder(before.newVisits, before.lastExportAt);
  expect(localStorage.getItem(EXPORT_REMINDER_DISMISS_KEY)).toBeTruthy();
  const after = await diaryExportReminder();
  expect(after.show).toBe(false);
});
