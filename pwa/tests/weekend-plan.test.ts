import { expect, test } from "vitest";
import type { CatalogPlace } from "../src/catalog/types";
import {
  greedyOrder,
  reorderPlaceIds,
  suggestWeekendPlaces,
  weekendCandidates,
} from "../src/diary/weekendPlan";

function place(id: string, name: string, lat: number, lon: number, region = "Olomoucký kraj"): CatalogPlace {
  return {
    id,
    name,
    short_name: null,
    alternative_names: [],
    types: ["CASTLE"],
    condition: "PRESERVED",
    visitability: "REGULAR",
    short_description: null,
    heritage_status: "NKP",
    unesco: false,
    location: {
      latitude: lat,
      longitude: lon,
      address: null,
      municipality: name,
      district: "Olomouc",
      region,
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
}

const origin = { latitude: 49.704, longitude: 16.891 };
const near = place("a", "Blízko", 49.71, 16.9);
const mid = place("b", "Střed", 49.75, 17.05);
const far = place("c", "Daleko", 50.08, 14.42, "Hlavní město Praha");

test("víkend bere jen wishlist v okruhu a seřadí greedy od startu", () => {
  const wantIds = new Set(["a", "b", "c"]);
  const suggested = suggestWeekendPlaces({
    places: [far, mid, near],
    wantIds,
    origin,
    radiusKm: 40,
    stopCount: 3,
  });
  expect(suggested.map((item) => item.id)).toEqual(["a", "b"]);
});

test("kraj odfiltruje Prahu i bez poloměru", () => {
  const wantIds = new Set(["a", "c"]);
  const pool = weekendCandidates({
    places: [near, far],
    wantIds,
    origin: null,
    region: "Olomoucký kraj",
    radiusKm: 150,
    stopCount: 3,
  });
  expect(pool.map((item) => item.id)).toEqual(["a"]);
});

test("greedy od startu bere nejbližší další", () => {
  const ordered = greedyOrder([mid, near, far], origin);
  expect(ordered[0]?.id).toBe("a");
});

test("reorderPlaceIds doplní místa bez GPS na konec", () => {
  const noGps = place("d", "Bez GPS", 49.7, 16.8);
  noGps.location = { ...noGps.location, latitude: null, longitude: null };
  const places = new Map([
    [near.id, near],
    [mid.id, mid],
    [noGps.id, noGps],
  ]);
  const ordered = reorderPlaceIds(["d", "b", "a"], places, origin);
  expect(ordered[0]).toBe("a");
  expect(ordered.at(-1)).toBe("d");
});

test("víkend vyřadí místo zavřené v plánovaný den", () => {
  const winterClosed = place("w", "Zima", 49.71, 16.9);
  winterClosed.osm_opening_hours = "Apr-Oct Mo-Su 09:00-17:00";
  const wantIds = new Set(["w", "a"]);
  const suggested = suggestWeekendPlaces({
    places: [winterClosed, near],
    wantIds,
    origin,
    radiusKm: 40,
    stopCount: 3,
    plannedOn: "2026-01-15",
  });
  expect(suggested.map((item) => item.id)).toEqual(["a"]);
});
