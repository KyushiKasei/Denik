import "fake-indexeddb/auto";
import { expect, test } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { diffPlaces } from "../src/catalog/diff";
import { catalogVersionAlreadyLoaded, previewCatalogImport, replacePlacesStore, loadPlaces, invalidatePlacesCache } from "../src/catalog/importCatalog";
import type { Catalog, CatalogPlace, StoredVisit } from "../src/catalog/types";
import { loadCatalogFromText } from "../src/catalog/validate";
import { db } from "../src/db";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const sample = loadCatalogFromText(readFileSync(path.join(repoRoot, "fixtures/catalog.sample.json"), "utf8"));

const FIXTURE_VISIT: StoredVisit = {
  id: "0198f93b-618d-762f-a589-ccf375139dd9",
  place_id: "0198f23a-5e5e-7b31-a8be-8c99507a2138",
  visited_at: "2026-08-09",
  rating: 5,
  people: ["Petr"],
  note: "fixture mimo UI",
  created_at: "2026-08-09T18:20:00+02:00",
  updated_at: "2026-08-09T18:20:00+02:00",
  deleted_at: null,
};

function withPlaces(places: CatalogPlace[], catalogVersion = 18): Catalog {
  return { ...sample, catalog_version: catalogVersion, places };
}

test("validní catalog se uloží do IndexedDB", async () => {
  await replacePlacesStore(sample);
  const places = await db.places.toArray();
  const meta = await db.meta.get("catalog_version");
  expect(places).toHaveLength(1);
  expect(places[0]?.name).toBe("Bouzov");
  expect(meta?.value).toBe(17);
});

test("diff spočítá nová, změněná a zmizelá id", () => {
  const current = sample.places;
  const renamed: CatalogPlace = { ...current[0], name: "Hrad Bouzov" };
  const extra: CatalogPlace = {
    ...current[0],
    id: "0198f23a-5e5e-7b31-a8be-8c99507a2139",
    name: "Karlštejn",
  };
  const diff = diffPlaces(current, [renamed, extra]);
  expect(diff.added).toBe(1);
  expect(diff.changed).toBe(1);
  expect(diff.removed).toBe(0);
  expect(diff.unchanged).toBe(0);
});

test("náhrada katalogu se nedotkne visits ani place_states", async () => {
  await db.visits.put(FIXTURE_VISIT);
  await db.place_states.put({
    place_id: FIXTURE_VISIT.place_id,
    want_to_visit: true,
    favorite: false,
    personal_note: "nesmazat",
    updated_at: "2026-08-09T18:20:00+02:00",
    deleted_at: null,
  });

  await replacePlacesStore(sample);
  const extra: CatalogPlace = {
    ...sample.places[0],
    id: "0198f23a-5e5e-7b31-a8be-8c99507a2140",
    name: "Bečov",
    types: ["CASTLE", "CHATEAU"],
  };
  await replacePlacesStore(withPlaces([...sample.places, extra], 19));

  const visit = await db.visits.get(FIXTURE_VISIT.id);
  const state = await db.place_states.get(FIXTURE_VISIT.place_id);
  expect(visit).toEqual(FIXTURE_VISIT);
  expect(state?.personal_note).toBe("nesmazat");
  expect(await db.visits.count()).toBe(1);
  expect(await db.places.count()).toBe(2);
});

test("druhý import nepřepíše deníkový store s fixture návštěvou", async () => {
  await db.visits.put(FIXTURE_VISIT);
  await replacePlacesStore(sample);
  await replacePlacesStore(sample);
  expect(await db.visits.toArray()).toEqual([FIXTURE_VISIT]);
});

test("náhled před zápisem vrátí počty proti aktuálnímu store", async () => {
  await replacePlacesStore(sample);
  const extra: CatalogPlace = { ...sample.places[0], id: "0198f23a-5e5e-7b31-a8be-8c99507a2141", name: "Křivoklát" };
  const diff = await previewCatalogImport(withPlaces([extra], 20));
  expect(diff.added).toBe(1);
  expect(diff.removed).toBe(1);
  expect(diff.changed).toBe(0);
});

test("stejná catalog_version už je nahraná", () => {
  expect(catalogVersionAlreadyLoaded(null, 17)).toBe(false);
  expect(catalogVersionAlreadyLoaded(17, 17)).toBe(true);
  expect(catalogVersionAlreadyLoaded(17, 18)).toBe(false);
});

test("loadPlaces po importu nenechá cache na starém toArray", async () => {
  await replacePlacesStore(sample);
  invalidatePlacesCache();
  const extra: CatalogPlace = {
    ...sample.places[0],
    id: "0198f23a-5e5e-7b31-a8be-8c99507a2142",
    name: "Karlštejn",
  };
  const newer = withPlaces([extra], 21);
  const originalToArray = db.places.toArray.bind(db.places) as () => Promise<CatalogPlace[]>;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let delayNext = true;
  (db.places as { toArray: () => Promise<CatalogPlace[]> }).toArray = async () => {
    if (delayNext) {
      delayNext = false;
      await gate;
    }
    return originalToArray();
  };
  try {
    const pending = loadPlaces();
    await replacePlacesStore(newer);
    release();
    await pending;
    expect((await loadPlaces())[0]?.name).toBe("Karlštejn");
  } finally {
    (db.places as { toArray: () => Promise<CatalogPlace[]> }).toArray = originalToArray;
  }
});
