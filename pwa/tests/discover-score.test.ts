import { expect, test } from "vitest";
import type { CatalogPlace } from "../src/catalog/types";
import { discoverScore } from "../src/diary/today";

const place = (id: string, patch: Partial<CatalogPlace> = {}): CatalogPlace => ({
  id,
  name: id,
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
    ...(patch.location ?? {}),
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
  ...patch,
});

test("objevování preferuje výlet a chybějící kraj, zavřené penalizuje", () => {
  const onTrip = place("trip");
  const missingRegion = place("miss", { location: { latitude: 49.7, longitude: 16.8, address: null, municipality: "x", district: "x", region: "Jihomoravský kraj", country: "CZ" } });
  const closed = place("shut", { visitability: "CLOSED" });
  const ctx = { tripPlaceIds: new Set(["trip"]), visitedRegionIds: new Set(["OLK"]), month: 8 };
  expect(discoverScore(onTrip, ctx)).toBeGreaterThan(discoverScore(missingRegion, ctx));
  expect(discoverScore(missingRegion, ctx)).toBeGreaterThan(discoverScore(closed, ctx));
});

test("zaniklý a pozůstatky mají nejnižší skóre, slabý stub je pod zachovalým", () => {
  const kept = place("hrad");
  const stub = place("stub", { heritage_status: "NONE", visitability: "UNKNOWN", condition: "UNKNOWN" });
  const extinct = place("tráva", { condition: "EXTINCT", visitability: "EXTINCT", heritage_status: "NONE" });
  expect(discoverScore(kept)).toBeGreaterThan(discoverScore(stub));
  expect(discoverScore(stub)).toBeGreaterThan(discoverScore(extinct));
  expect(discoverScore(extinct)).toBe(-1000);
});
