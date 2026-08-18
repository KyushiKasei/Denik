import { expect, test } from "vitest";
import { clampRadiusKm, DEFAULT_RADIUS_KM, haversineKm, MAX_RADIUS_KM, MIN_RADIUS_KM } from "../src/geo/haversine";
import { placesNearby, MAX_NEARBY_HITS, capNearbyHits } from "../src/geo/nearby";
import { resolveOriginFromCatalog, suggestOrigins } from "../src/geo/origin";
import type { CatalogPlace } from "../src/catalog/types";

const bouzov: CatalogPlace = {
  id: "1",
  name: "Bouzov",
  short_name: null,
  alternative_names: ["Hrad Bouzov"],
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
  types: ["CHATEAU"],
  location: { ...bouzov.location, latitude: 49.704, longitude: 17.03, municipality: "Loštice" },
};

const prague: CatalogPlace = {
  ...bouzov,
  id: "3",
  name: "Praha",
  types: ["PALACE"],
  location: {
    ...bouzov.location,
    latitude: 50.087,
    longitude: 14.421,
    municipality: "Praha",
    district: "Praha",
    region: "Hlavní město Praha",
  },
};

const noGps: CatalogPlace = {
  ...bouzov,
  id: "4",
  name: "Bez GPS",
  location: { ...bouzov.location, latitude: null, longitude: null },
};

const emptyFilters = { query: "", type: "" as const, region: "", district: "", journal: "" as const };

test("haversine km matches matching.py earth radius formula", () => {
  const km = haversineKm(49.704, 16.891, 49.704, 17.03);
  expect(km).not.toBeNull();
  expect(km ?? 0).toBeGreaterThan(9);
  expect(km ?? 0).toBeLessThan(12);
  expect(haversineKm(null, 16.8, 49.7, 16.8)).toBeNull();
});

test("clamp radius", () => {
  expect(clampRadiusKm(null)).toBe(DEFAULT_RADIUS_KM);
  expect(clampRadiusKm(1)).toBe(MIN_RADIUS_KM);
  expect(clampRadiusKm(999)).toBe(MAX_RADIUS_KM);
});

test("nearby orders by km, drops far and missing GPS", () => {
  const origin = { latitude: 49.704, longitude: 16.891 };
  const { hits, skippedNoGps } = placesNearby([bouzov, near, prague, noGps], origin, 30, emptyFilters);
  expect(hits.map((item) => item.place.name)).toEqual(["Bouzov", "Blízko"]);
  expect(hits[0]!.km).toBeLessThan(hits[1]!.km);
  expect(skippedNoGps).toBe(1);
  const tight = placesNearby([bouzov, near, prague, noGps], origin, 5, emptyFilters);
  expect(tight.hits.map((item) => item.place.name)).toEqual(["Bouzov"]);
});

test("nearby type filter", () => {
  const origin = { latitude: 49.704, longitude: 16.891 };
  const { hits } = placesNearby([bouzov, near], origin, 30, { ...emptyFilters, type: "CASTLE" });
  expect(hits.map((item) => item.place.name)).toEqual(["Bouzov"]);
});

test("nearby region filter", () => {
  const origin = { latitude: 49.704, longitude: 16.891 };
  const { hits } = placesNearby([bouzov, near, prague], origin, 150, {
    ...emptyFilters,
    region: "Olomoucký kraj",
  });
  expect(hits.map((item) => item.place.name)).toEqual(["Bouzov", "Blízko"]);
});

test("nearby not visited", () => {
  const origin = { latitude: 49.704, longitude: 16.891 };
  const diary = { visitedIds: new Set(["1"]), wantIds: new Set(["2"]) };
  const { hits } = placesNearby([bouzov, near], origin, 30, { ...emptyFilters, journal: "not_visited" }, diary);
  expect(hits.map((item) => item.place.name)).toEqual(["Blízko"]);
});

test("origin from catalog name and municipality", () => {
  expect(resolveOriginFromCatalog([bouzov], "Bouzov")?.source).toBe("place");
  expect(resolveOriginFromCatalog([bouzov], "bouzov")?.latitude).toBe(49.704);
  expect(suggestOrigins([bouzov], "Bou").map((item) => item.label)).toEqual(["Bouzov"]);
  expect(suggestOrigins([bouzov], "Bo")).toEqual([]);
});

test("Praha padá na střed města, ne na první zámek v obci", () => {
  const hlubocepy: CatalogPlace = {
    ...prague,
    id: "h",
    name: "zámek Hlubočepy",
    location: { ...prague.location, latitude: 50.04, longitude: 14.397, municipality: "Praha" },
  };
  const origin = resolveOriginFromCatalog([hlubocepy, prague], "Praha");
  expect(origin?.label).toBe("Praha");
  expect(origin?.source).toBe("municipality");
  expect(origin?.latitude).toBeCloseTo(50.0875, 3);
  expect(origin?.longitude).toBeCloseTo(14.4213, 3);
  expect(suggestOrigins([hlubocepy], "Praha")[0]?.label).toBe("Praha");
});

test("nearby cap nechá nejbližší", () => {
  const origin = { latitude: 49.704, longitude: 16.891 };
  const many = Array.from({ length: MAX_NEARBY_HITS + 3 }, (_, index) => ({
    ...bouzov,
    id: String(index),
    name: `Místo ${String(index).padStart(3, "0")}`,
    location: { ...bouzov.location, longitude: 16.891 + index * 0.001 },
  }));
  const { hits, hitsTotal } = placesNearby(many, origin, 150, emptyFilters);
  expect(hitsTotal).toBe(MAX_NEARBY_HITS + 3);
  expect(hits).toHaveLength(MAX_NEARBY_HITS);
  expect(hits[0]?.place.name).toBe("Místo 000");
  expect(capNearbyHits([{ place: bouzov, km: 1 }]).hitsTotal).toBe(1);
});
