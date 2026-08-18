import { expect, test } from "vitest";
import { facetCounts } from "../src/catalog/filterPlaces";
import { distanceToSegmentKm, placesAlongCorridor, placesInCorridor } from "../src/geo/corridor";
import type { CatalogPlace } from "../src/catalog/types";

function place(id: string, name: string, lat: number, lon: number): CatalogPlace {
  return {
    id,
    name,
    short_name: null,
    alternative_names: [],
    types: ["CASTLE"],
    condition: "PRESERVED",
    visitability: "REGULAR",
    short_description: null,
    heritage_status: null,
    unesco: false,
    location: {
      latitude: lat,
      longitude: lon,
      address: null,
      municipality: name,
      district: null,
      region: null,
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

const prague = { latitude: 50.087, longitude: 14.421 };
const brno = { latitude: 49.195, longitude: 16.608 };
const emptyFilters = { query: "", type: "" as const, region: "", district: "", journal: "" as const };

test("bod na úsečce má vzdálenost ~0", () => {
  const mid = { latitude: (prague.latitude + brno.latitude) / 2, longitude: (prague.longitude + brno.longitude) / 2 };
  const km = distanceToSegmentKm(mid, prague, brno);
  expect(km).not.toBeNull();
  expect(km ?? 99).toBeLessThan(2);
});

test("koridor Praha–Brno vezme místo u čáry a vynechá daleko", () => {
  const along = place("1", "Na cestě", 49.6, 15.5);
  const aside = place("2", "Bokem", 50.5, 14.0);
  const { hits } = placesAlongCorridor([along, aside], prague, brno, 20, emptyFilters);
  expect(hits.map((item) => item.place.name)).toEqual(["Na cestě"]);
});

test("filtry koridoru počítají místa u čáry, ne hledání polohy", () => {
  const alongCastle = place("1", "Na cestě", 49.6, 15.5);
  const alongChateau: CatalogPlace = { ...place("3", "Zámek u cesty", 49.61, 15.52), types: ["CHATEAU"] };
  const aside = place("2", "Bokem", 50.5, 14.0);
  const inCorridor = placesInCorridor([alongCastle, alongChateau, aside], prague, brno, 20);
  expect(inCorridor.map((item) => item.name).sort((a, b) => a.localeCompare(b, "cs"))).toEqual([
    "Na cestě",
    "Zámek u cesty",
  ]);

  const leaked = facetCounts(inCorridor, { ...emptyFilters, query: "Moje poloha" });
  expect(leaked.types[""]).toBe(0);

  const mapFacets = facetCounts(inCorridor, { ...emptyFilters, query: "" });
  expect(mapFacets.types[""]).toBe(2);
  expect(mapFacets.types.CASTLE).toBe(1);
  expect(mapFacets.types.CHATEAU).toBe(1);

  const typedHits = placesAlongCorridor([alongCastle, alongChateau, aside], prague, brno, 20, {
    ...emptyFilters,
    type: "CASTLE",
  });
  expect(typedHits.hits.map((item) => item.place.name)).toEqual(["Na cestě"]);
  const afterType = facetCounts(inCorridor, { ...emptyFilters, type: "CASTLE" });
  expect(afterType.types.CASTLE).toBe(1);
  expect(afterType.types.CHATEAU).toBe(1);
});
