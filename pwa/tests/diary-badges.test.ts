import { expect, test } from "vitest";
import type { CatalogPlace, PlaceTypeCode, StoredVisit } from "../src/catalog/types";
import { badgesForDisplay, computeBadges } from "../src/diary/badges";

const basePlace: CatalogPlace = {
  id: "p0",
  name: "Místo",
  short_name: null,
  alternative_names: [],
  types: ["CASTLE"],
  condition: "PRESERVED",
  visitability: "REGULAR",
  short_description: null,
  heritage_status: "NKP",
  unesco: false,
  location: {
    latitude: 49.7,
    longitude: 16.8,
    address: null,
    municipality: "Obec",
    district: "Okres",
    region: "Olomoucký kraj",
    country: "CZ",
  },
  links: {
    official: null,
    wikipedia: null,
    wikidata: null,
    heritage_catalog: null,
    opening_hours: null,
    tickets: null,
  },
  image: null,
};

function place(id: string, patch: Partial<CatalogPlace> = {}): CatalogPlace {
  return {
    ...basePlace,
    ...patch,
    id,
    name: patch.name ?? `Místo ${id}`,
    location: { ...basePlace.location, ...(patch.location ?? {}) },
    types: patch.types ?? basePlace.types,
  };
}

function visit(placeId: string, extra: Partial<StoredVisit> = {}): StoredVisit {
  return {
    id: `v-${placeId}-${extra.visited_at ?? "1"}`,
    place_id: placeId,
    visited_at: "2026-08-09",
    rating: 4,
    people: [],
    note: null,
    created_at: "2026-08-09T10:00:00+02:00",
    updated_at: "2026-08-09T10:00:00+02:00",
    deleted_at: null,
    ...extra,
  };
}

function ids(badges: ReturnType<typeof computeBadges>, unlocked = true): string[] {
  return badges.filter((badge) => badge.unlocked === unlocked).map((badge) => badge.id);
}

test("bez návštěv není odemčený žádný odznak", () => {
  const badges = computeBadges([], [place("a")]);
  expect(ids(badges, true)).toEqual([]);
  expect(ids(badges, false)).toContain("first_visit");
  expect(badgesForDisplay(badges)).toEqual([]);
});

test("první návštěva, hrad a kraj z fixture", () => {
  const castle = place("c1", { types: ["CASTLE"], location: { ...basePlace.location, region: "Olomoucký kraj" } });
  const badges = computeBadges([visit("c1")], [castle]);
  expect(ids(badges)).toEqual(expect.arrayContaining(["first_visit", "first_castle", "regions"]));
  expect(badges.find((badge) => badge.id === "regions")?.title).toBe("Navštíveno 1 kraj");
  expect(ids(badges)).not.toContain("places_5");
  expect(ids(badges)).not.toContain("unesco");
});

test("smazaná návštěva se nepočítá", () => {
  const castle = place("c1");
  const badges = computeBadges([visit("c1", { deleted_at: "2026-08-10T00:00:00+02:00" })], [castle]);
  expect(ids(badges)).toEqual([]);
});

test("5 unikátních míst odemkne milník, 50 taky", () => {
  const places = Array.from({ length: 50 }, (_, i) => place(`p${i}`));
  const five = computeBadges(
    places.slice(0, 5).map((row) => visit(row.id)),
    places,
  );
  expect(ids(five)).toContain("places_5");
  expect(ids(five)).not.toContain("places_10");

  const fifty = computeBadges(
    places.map((row) => visit(row.id)),
    places,
  );
  expect(ids(fifty)).toEqual(
    expect.arrayContaining(["places_5", "places_10", "places_25", "places_50"]),
  );
});

test("UNESCO a první zámek", () => {
  const unescoChateau = place("u1", {
    types: ["CHATEAU"] as PlaceTypeCode[],
    unesco: true,
    location: { ...basePlace.location, region: "Jihomoravský kraj" },
  });
  const badges = computeBadges([visit("u1")], [unescoChateau]);
  expect(ids(badges)).toEqual(expect.arrayContaining(["unesco", "first_chateau", "first_visit"]));
  expect(ids(badges)).not.toContain("first_castle");
});

test("dva kraje v titulku, ne všechny kraje katalogu", () => {
  const a = place("a", { location: { ...basePlace.location, region: "Olomoucký kraj" } });
  const b = place("b", { location: { ...basePlace.location, region: "Středočeský kraj" } });
  const unused = place("c", { location: { ...basePlace.location, region: "Moravskoslezský kraj" } });
  const badges = computeBadges([visit("a"), visit("b")], [a, b, unused]);
  const regions = badges.find((badge) => badge.id === "regions");
  expect(regions?.title).toBe("Navštíveno 2 kraje");
  expect(regions?.detail).toContain("Olomoucký kraj");
  expect(regions?.detail).toContain("Středočeský kraj");
  expect(regions?.detail).not.toContain("Moravskoslezský kraj");
});

test("zobrazení drží odemčené a jen další milník", () => {
  const castle = place("c1");
  const shown = badgesForDisplay(computeBadges([visit("c1")], [castle]));
  expect(shown.some((badge) => badge.id === "first_visit" && badge.unlocked)).toBe(true);
  expect(shown.filter((badge) => badge.id.startsWith("places_")).map((badge) => badge.id)).toEqual(["places_5"]);
  expect(shown.find((badge) => badge.id === "places_5")?.unlocked).toBe(false);
});
