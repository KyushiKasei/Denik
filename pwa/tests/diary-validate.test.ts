import { expect, test } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { DiaryImportError } from "../src/diary/errors";
import { loadDiaryFromText, validateDiary } from "../src/diary/validate";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const sampleText = readFileSync(path.join(repoRoot, "fixtures/diary.sample.json"), "utf8");

function sampleDiary() {
  return JSON.parse(sampleText) as Record<string, unknown>;
}

test("validní diary.sample.json se načte", () => {
  const diary = loadDiaryFromText(sampleText);
  expect(diary.schema_version).toBe(1);
  expect(diary.trips).toEqual([]);
  expect(diary.visits[0]?.id).toBe("0198f93b-618d-762f-a589-ccf375139dd9");
  expect(diary.visits[0]?.deleted_at).toBeNull();
  expect(diary.place_states[0]?.updated_at).toBeTruthy();
});

test("nevalidní soubor se odmítne", () => {
  const invalid = { ...sampleDiary(), visits: "ne" };
  expect(() => validateDiary(invalid)).toThrow(DiaryImportError);
  expect(() => validateDiary(invalid)).toThrow(/Nevalidní diary\.json/);
});

test("neznámá schema_version se odmítne", () => {
  const unknown = { ...sampleDiary(), schema_version: 99 };
  expect(() => validateDiary(unknown)).toThrow(DiaryImportError);
  expect(() => validateDiary(unknown)).toThrow(/schema_version/);
});

test("schema_version 2 bez trips se odmítne", () => {
  const missingTrips = { ...sampleDiary(), schema_version: 2 };
  expect(() => validateDiary(missingTrips)).toThrow(/trips/);
});

test("schema_version 2 s výlety se načte", () => {
  const withTrips = {
    ...sampleDiary(),
    schema_version: 2,
    trips: [
      {
        id: "0198f93b-618d-762f-a589-ccf375139dd8",
        name: "Olomoucko",
        planned_on: "2026-08-20",
        origin: null,
        notes: null,
        stops: [
          {
            place_id: "0198f23a-5e5e-7b31-a8be-8c99507a2138",
            sort_order: 0,
            note: null,
          },
        ],
        created_at: "2026-08-16T10:00:00+02:00",
        updated_at: "2026-08-16T10:00:00+02:00",
        deleted_at: null,
      },
    ],
  };
  const diary = validateDiary(withTrips);
  expect(diary.trips).toHaveLength(1);
  expect(diary.trips[0]?.name).toBe("Olomoucko");
});

test("integer visits[].id se odmítne", () => {
  const data = sampleDiary();
  const visits = data.visits as Array<Record<string, unknown>>;
  visits[0] = { ...visits[0], id: 1 };
  expect(() => validateDiary(data)).toThrow(DiaryImportError);
});

test("ne-JSON text se odmítne", () => {
  expect(() => loadDiaryFromText("{")).toThrow(/není platný JSON/);
});
