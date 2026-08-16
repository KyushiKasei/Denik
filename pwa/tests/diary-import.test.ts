import "fake-indexeddb/auto";
import { expect, test } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { replacePlacesStore } from "../src/catalog/importCatalog";
import type { StoredVisit } from "../src/catalog/types";
import { loadCatalogFromText } from "../src/catalog/validate";
import { db } from "../src/db";
import { addVisit, importDiary, loadVisits, loadVisitsForPlace, updateVisit } from "../src/diary/store";
import { loadDiaryFromText } from "../src/diary/validate";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const sampleDiary = loadDiaryFromText(readFileSync(path.join(repoRoot, "fixtures/diary.sample.json"), "utf8"));
const sampleCatalog = loadCatalogFromText(readFileSync(path.join(repoRoot, "fixtures/catalog.sample.json"), "utf8"));

const VISIT_B = "0198f93b-618d-762f-a589-ccf375139dda";

test("opakovaný import stejného diary.json nevytvoří duplicity", async () => {
  const first = await importDiary(sampleDiary);
  const second = await importDiary(sampleDiary);
  expect(first.visitsInserted).toBe(1);
  expect(second.visitsInserted).toBe(0);
  expect(second.visitsUpdated).toBe(0);
  expect(await db.visits.count()).toBe(1);
  expect(await db.place_states.count()).toBe(1);
});

test("dvě návštěvy stejného místa zůstanou dvě", async () => {
  const secondVisit: StoredVisit = {
    ...sampleDiary.visits[0],
    id: VISIT_B,
    visited_at: "2026-08-10",
    note: "Druhá návštěva.",
  };
  await importDiary({ ...sampleDiary, visits: [...sampleDiary.visits, secondVisit] });
  const rows = await loadVisitsForPlace(sampleDiary.visits[0].place_id);
  expect(rows).toHaveLength(2);
  expect(new Set(rows.map((row) => row.id)).size).toBe(2);
});

test("aktualizace katalogu nesmaže návštěvy", async () => {
  await importDiary(sampleDiary);
  await replacePlacesStore(sampleCatalog);
  await replacePlacesStore({
    ...sampleCatalog,
    catalog_version: 18,
    places: [
      sampleCatalog.places[0],
      { ...sampleCatalog.places[0], id: "0198f23a-5e5e-7b31-a8be-8c99507a2140", name: "Bečov" },
    ],
  });
  const visits = await loadVisits(true);
  expect(visits).toHaveLength(1);
  expect(visits[0]?.id).toBe(sampleDiary.visits[0].id);
  expect(visits[0]?.note).toBe("Výborná prohlídka.");
  expect(await db.places.count()).toBe(2);
});

test("přidání návštěvy vygeneruje nové id a druhé místo má víc záznamů", async () => {
  await replacePlacesStore(sampleCatalog);
  const placeId = sampleCatalog.places[0].id;
  const first = await addVisit({ place_id: placeId, visited_at: "2026-08-09", rating: 5, people: "Jana, Petr", note: "A" });
  const second = await addVisit({ place_id: placeId, visited_at: "2026-08-10", rating: 4, people: "Petr", note: "B" });
  expect(first.id).not.toBe(second.id);
  expect(first.id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  const rows = await loadVisitsForPlace(placeId);
  expect(rows).toHaveLength(2);
});

test("novější updated_at vyhraje včetně soft-delete", async () => {
  await importDiary(sampleDiary);
  const deleted = {
    ...sampleDiary,
    visits: [
      {
        ...sampleDiary.visits[0],
        note: "smazáno",
        updated_at: "2026-08-10T12:00:00+02:00",
        deleted_at: "2026-08-10T12:00:00+02:00",
      },
    ],
  };
  const result = await importDiary(deleted);
  expect(result.visitsUpdated).toBe(1);
  const hidden = await loadVisits();
  expect(hidden).toHaveLength(0);
  const all = await loadVisits(true);
  expect(all[0]?.deleted_at).toBe("2026-08-10T12:00:00+02:00");
});

test("úprava návštěvy změní datum a poznámku", async () => {
  await replacePlacesStore(sampleCatalog);
  const placeId = sampleCatalog.places[0].id;
  const created = await addVisit({ place_id: placeId, visited_at: "2026-08-09", rating: 5, people: "Petr", note: "A" });
  await updateVisit(created.id, { visited_at: "2026-08-10", rating: 4, people: "Jana, Petr", note: "upraveno" });
  const rows = await loadVisitsForPlace(placeId);
  expect(rows).toHaveLength(1);
  expect(rows[0]?.visited_at).toBe("2026-08-10");
  expect(rows[0]?.rating).toBe(4);
  expect(rows[0]?.people).toEqual(["Jana", "Petr"]);
  expect(rows[0]?.note).toBe("upraveno");
  expect(rows[0]?.id).toBe(created.id);
});

test("výlet se sloučí podle id a opakovaný import nevytvoří duplicitu", async () => {
  const trip = {
    id: "0198f93b-618d-762f-a589-ccf375139dd8",
    name: "Olomoucko",
    planned_on: "2026-08-20",
    origin: null,
    notes: null,
    stops: [
      {
        place_id: sampleDiary.visits[0].place_id,
        sort_order: 0,
        note: null,
      },
    ],
    created_at: "2026-08-16T10:00:00+02:00",
    updated_at: "2026-08-16T10:00:00+02:00",
    deleted_at: null,
  };
  const payload = { ...sampleDiary, schema_version: 2, trips: [trip] };
  const first = await importDiary(payload);
  const second = await importDiary(payload);
  expect(first.tripsInserted).toBe(1);
  expect(second.tripsInserted).toBe(0);
  expect(second.tripsUpdated).toBe(0);
  expect(await db.trips.count()).toBe(1);
});

test("výlet přežije aktualizaci katalogu i neznámé místo v zastávce", async () => {
  const unknownPlace = "0198f23a-5e5e-7b31-a8be-8c99507a9999";
  await importDiary({
    ...sampleDiary,
    schema_version: 2,
    trips: [
      {
        id: "0198f93b-618d-762f-a589-ccf375139dd8",
        name: "S osiřelou zastávkou",
        planned_on: null,
        origin: null,
        notes: null,
        stops: [{ place_id: unknownPlace, sort_order: 0, note: null }],
        created_at: "2026-08-16T10:00:00+02:00",
        updated_at: "2026-08-16T10:00:00+02:00",
        deleted_at: null,
      },
    ],
  });
  await replacePlacesStore(sampleCatalog);
  const trips = await db.trips.toArray();
  expect(trips).toHaveLength(1);
  expect(trips[0]?.stops[0]?.place_id).toBe(unknownPlace);
  expect(await db.places.where("id").equals(unknownPlace).count()).toBe(0);
});

test("smazaný výlet se znovu nevloží ze staršího souboru", async () => {
  const tripId = "0198f93b-618d-762f-a589-ccf375139dd8";
  await importDiary({
    ...sampleDiary,
    schema_version: 2,
    trips: [
      {
        id: tripId,
        name: "Smazaný",
        planned_on: null,
        origin: null,
        notes: null,
        stops: [],
        created_at: "2026-08-16T10:00:00+02:00",
        updated_at: "2026-08-17T10:00:00+02:00",
        deleted_at: "2026-08-17T10:00:00+02:00",
      },
    ],
  });
  const older = await importDiary({
    ...sampleDiary,
    schema_version: 2,
    trips: [
      {
        id: tripId,
        name: "Smazaný",
        planned_on: null,
        origin: null,
        notes: null,
        stops: [],
        created_at: "2026-08-16T10:00:00+02:00",
        updated_at: "2026-08-16T10:00:00+02:00",
        deleted_at: null,
      },
    ],
  });
  expect(older.tripsUpdated).toBe(0);
  const row = await db.trips.get(tripId);
  expect(row?.deleted_at).toBe("2026-08-17T10:00:00+02:00");
});
