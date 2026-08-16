import "fake-indexeddb/auto";
import { expect, test } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { replacePlacesStore } from "../src/catalog/importCatalog";
import type { Catalog, CatalogPlace, StoredPlaceState, StoredVisit } from "../src/catalog/types";
import { loadCatalogFromText } from "../src/catalog/validate";
import { countVisitsForRemovedPlaces, groupOrphans, listOrphanedDiary } from "../src/diary/orphans";
import { addVisit, exportDiary, loadVisits } from "../src/diary/store";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const sampleCatalog = loadCatalogFromText(readFileSync(path.join(repoRoot, "fixtures/catalog.sample.json"), "utf8"));

const PLACE_ID = sampleCatalog.places[0].id;

const VISIT: StoredVisit = {
  id: "0198f93b-618d-762f-a589-ccf375139dd9",
  place_id: PLACE_ID,
  visited_at: "2026-08-09",
  rating: 5,
  people: ["Petr"],
  note: "fixture",
  created_at: "2026-08-09T18:20:00+02:00",
  updated_at: "2026-08-09T18:20:00+02:00",
  deleted_at: null,
};

function emptyCatalog(version: number): Catalog {
  return { ...sampleCatalog, catalog_version: version, places: [] };
}

function withPlaces(places: CatalogPlace[], version: number): Catalog {
  return { ...sampleCatalog, catalog_version: version, places };
}

test("groupOrphans označí návštěvy u id, které v katalogu nejsou", () => {
  const state: StoredPlaceState = {
    place_id: PLACE_ID,
    want_to_visit: true,
    favorite: false,
    personal_note: null,
    updated_at: "2026-08-09T18:20:00+02:00",
    deleted_at: null,
  };
  const groups = groupOrphans([VISIT], [state], new Set());
  expect(groups).toHaveLength(1);
  expect(groups[0]?.place_id).toBe(PLACE_ID);
  expect(groups[0]?.visits).toHaveLength(1);
  expect(groups[0]?.state?.want_to_visit).toBe(true);
  expect(groupOrphans([VISIT], [state], new Set([PLACE_ID]))).toHaveLength(0);
});

test("countVisitsForRemovedPlaces počítá jen aktivní návštěvy zmizelých id", () => {
  const deleted: StoredVisit = { ...VISIT, id: "0198f93b-618d-762f-a589-ccf375139dda", deleted_at: "2026-08-10T12:00:00+02:00" };
  expect(countVisitsForRemovedPlaces([VISIT, deleted], [PLACE_ID])).toBe(1);
  expect(countVisitsForRemovedPlaces([VISIT], ["other"])).toBe(0);
});

test("aktualizace katalogu bez místa nechá návštěvy a označí je jako osiřelé", async () => {
  await replacePlacesStore(sampleCatalog);
  await addVisit({ place_id: PLACE_ID, visited_at: "2026-08-09", rating: 5, people: "Jana, Petr", note: "A" });
  await addVisit({ place_id: PLACE_ID, visited_at: "2026-08-11", rating: 4, people: "Petr", note: "B" });

  const diary = await exportDiary();
  expect(diary.visits.filter((visit) => !visit.deleted_at)).toHaveLength(2);

  await replacePlacesStore(emptyCatalog(18));
  const visits = await loadVisits();
  expect(visits).toHaveLength(2);
  expect(visits.map((visit) => visit.note).sort()).toEqual(["A", "B"]);

  const orphans = await listOrphanedDiary();
  expect(orphans).toHaveLength(1);
  expect(orphans[0]?.place_id).toBe(PLACE_ID);
  expect(orphans[0]?.visits).toHaveLength(2);
  expect(orphans[0]?.last_name).toBe(sampleCatalog.places[0].name);
});

test("návštěva u místa, které v novém catalog.json zbývá, osiřelá není", async () => {
  await replacePlacesStore(sampleCatalog);
  await addVisit({ place_id: PLACE_ID, visited_at: "2026-08-09", rating: 5, people: "", note: "ok" });
  const extra: CatalogPlace = { ...sampleCatalog.places[0], id: "0198f23a-5e5e-7b31-a8be-8c99507a2140", name: "Bečov" };
  await replacePlacesStore(withPlaces([sampleCatalog.places[0], extra], 19));
  expect(await listOrphanedDiary()).toHaveLength(0);
});
