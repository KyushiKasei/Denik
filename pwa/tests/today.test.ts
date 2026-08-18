import { expect, test } from "vitest";
import type { CatalogPlace, StoredVisit } from "../src/catalog/types";
import { lastActiveVisit, nearbyUnvisited, pickDiscoverToday } from "../src/diary/today";

const bouzov: CatalogPlace = {
  id: "1",
  name: "Bouzov",
  short_name: null,
  alternative_names: [],
  types: ["CASTLE"],
  condition: "PRESERVED",
  visitability: "REGULAR",
  short_description: null,
  heritage_status: "NKP",
  unesco: false,
  location: {
    latitude: 49.704,
    longitude: 16.891,
    address: null,
    municipality: "Bouzov",
    district: "Olomouc",
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

const near: CatalogPlace = {
  ...bouzov,
  id: "2",
  name: "Blízko",
  location: { ...bouzov.location, longitude: 17.03, municipality: "Loštice" },
};

const far: CatalogPlace = {
  ...bouzov,
  id: "3",
  name: "Daleko",
  location: { ...bouzov.location, latitude: 50.08, longitude: 14.44, region: "Hlavní město Praha" },
};

function visit(placeId: string, visitedAt: string, extra: Partial<StoredVisit> = {}): StoredVisit {
  return {
    id: `v-${placeId}-${visitedAt}`,
    place_id: placeId,
    visited_at: visitedAt,
    rating: null,
    people: [],
    note: null,
    created_at: `${visitedAt}T10:00:00+02:00`,
    updated_at: `${visitedAt}T10:00:00+02:00`,
    deleted_at: null,
    ...extra,
  };
}

const origin = { latitude: 49.704, longitude: 16.891 };

test("poslední návštěva je nejnovější živá", () => {
  const last = lastActiveVisit([
    visit("1", "2026-01-01"),
    visit("2", "2026-08-10"),
    visit("3", "2026-08-11", { deleted_at: "2026-08-12T00:00:00+02:00" }),
  ]);
  expect(last?.place_id).toBe("2");
});

test("nearbyUnvisited vynechá navštívené a vzdálené", () => {
  const hits = nearbyUnvisited([bouzov, near, far], origin, 30, [visit("1", "2026-08-09")], 5);
  expect(hits.map((hit) => hit.place.id)).toEqual(["2"]);
});

test("Objevte dnes je v jeden den stejné místo", () => {
  const a = pickDiscoverToday([bouzov, near, far], [], origin, 30, "2026-08-17");
  const b = pickDiscoverToday([bouzov, near, far], [], origin, 30, "2026-08-17");
  expect(a?.id).toBe(b?.id);
  expect(a).not.toBeNull();
});

test("skip vybere jiné místo, po vyčerpání znovu pool", () => {
  const first = pickDiscoverToday([bouzov, near], [], origin, 30, "2026-08-17");
  expect(first).not.toBeNull();
  const second = pickDiscoverToday([bouzov, near], [], origin, 30, "2026-08-17", new Set([first!.id]));
  expect(second?.id).not.toBe(first?.id);
});

test("Objevte dnes a nearby vynechají zaniklý hrad", () => {
  const grass: CatalogPlace = {
    ...bouzov,
    id: "9",
    name: "Tráva",
    condition: "EXTINCT",
    visitability: "EXTINCT",
    heritage_status: "NONE",
    location: { ...bouzov.location, longitude: 16.9 },
  };
  expect(pickDiscoverToday([grass], [], origin, 30, "2026-08-17")).toBeNull();
  expect(nearbyUnvisited([grass, near], origin, 30, [], 5).map((hit) => hit.place.id)).toEqual(["2"]);
});

test("nálada dne omezí nearby i Objevte", () => {
  const ruin: CatalogPlace = {
    ...near,
    id: "8",
    name: "Trosky",
    types: ["RUIN"],
    condition: "RUIN",
    visitability: "FREE_ACCESS",
  };
  expect(nearbyUnvisited([bouzov, ruin], origin, 30, [], 5, "ruins").map((hit) => hit.place.id)).toEqual(["8"]);
  expect(pickDiscoverToday([bouzov, ruin], [], origin, 30, "2026-08-17", new Set(), {}, "ruins")?.id).toBe("8");
});
