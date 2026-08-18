import { expect, test } from "vitest";
import type { StoredVisit } from "../src/catalog/types";
import { uniquePeopleNames, visitHasPerson } from "../src/diary/people";
import { visitsNeedingFollowUp } from "../src/diary/inbox";

function visit(over: Partial<StoredVisit> = {}): StoredVisit {
  return {
    id: "1",
    place_id: "p",
    visited_at: "2026-08-09",
    rating: null,
    people: ["Jana", "Petr"],
    note: "ok",
    created_at: "2026-08-09T10:00:00+02:00",
    updated_at: "2026-08-09T10:00:00+02:00",
    deleted_at: null,
    ...over,
  };
}

test("jména lidí jsou unikátní a řazená", () => {
  expect(uniquePeopleNames([visit(), visit({ id: "2", people: ["Eva", "Petr"] })])).toEqual(["Eva", "Jana", "Petr"]);
});

test("filtr podle osoby je case-insensitive česky", () => {
  expect(visitHasPerson(visit(), "jana")).toBe(true);
  expect(visitHasPerson(visit(), "Eva")).toBe(false);
});

test("inbox bere návštěvy bez fotky nebo poznámky", () => {
  const rows = visitsNeedingFollowUp(
    [visit(), visit({ id: "2", note: null, people: [] }), visit({ id: "3", note: "x", people: [] })],
    new Map([
      ["1", 1],
      ["3", 0],
    ]),
  );
  expect(rows.map((row) => row.visit.id)).toEqual(["2", "3"]);
});
