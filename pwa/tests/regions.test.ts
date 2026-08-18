import { expect, test } from "vitest";
import type { CatalogPlace, StoredVisit } from "../src/catalog/types";
import {
  CZECH_REGIONS,
  collectionStats,
  matchCzechRegion,
  regionProgress,
  unlockedRegionCount,
} from "../src/diary/regions";

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
    location: { ...basePlace.location, ...(patch.location ?? {}) },
  };
}

function visit(placeId: string): StoredVisit {
  return {
    id: `v-${placeId}`,
    place_id: placeId,
    visited_at: "2026-08-09",
    rating: null,
    people: [],
    note: null,
    created_at: "2026-08-09T10:00:00+02:00",
    updated_at: "2026-08-09T10:00:00+02:00",
    deleted_at: null,
  };
}

test("14 krajů a aliasy názvů", () => {
  expect(CZECH_REGIONS).toHaveLength(14);
  expect(matchCzechRegion("Olomoucký kraj")?.id).toBe("OLK");
  expect(matchCzechRegion("olomoucky")?.id).toBe("OLK");
  expect(matchCzechRegion("Praha")?.id).toBe("PHA");
  expect(matchCzechRegion("Hlavní město Praha")?.id).toBe("PHA");
  expect(matchCzechRegion("Vysočina")?.id).toBe("VYS");
  expect(matchCzechRegion("Kraj Vysočina")?.id).toBe("VYS");
  expect(matchCzechRegion("Atlantis")).toBeNull();
});

test("progress počítá jen navštívené kraje", () => {
  const olk = place("a");
  const stc = place("b", { location: { ...basePlace.location, region: "Středočeský kraj" } });
  const unused = place("c", { location: { ...basePlace.location, region: "Moravskoslezský kraj" } });
  const rows = regionProgress([olk, stc, unused], [visit("a"), visit("b")]);
  expect(unlockedRegionCount(rows)).toBe(2);
  expect(rows.find((row) => row.region.id === "OLK")?.visited).toBe(1);
  expect(rows.find((row) => row.region.id === "MSK")?.unlocked).toBe(false);
});

test("sbírky NKP / UNESCO / zříceniny", () => {
  const nkp = place("n", { heritage_status: "NKP" });
  const unesco = place("u", { unesco: true, heritage_status: "KP" });
  const ruin = place("r", { types: ["RUIN"], heritage_status: "NONE" });
  const stats = collectionStats([nkp, unesco, ruin], [visit("n"), visit("r")]);
  expect(stats.find((row) => row.id === "nkp")).toEqual({ id: "nkp", title: "NKP", visited: 1, total: 1 });
  expect(stats.find((row) => row.id === "unesco")).toEqual({ id: "unesco", title: "UNESCO", visited: 0, total: 1 });
  expect(stats.find((row) => row.id === "ruin")).toEqual({ id: "ruin", title: "Zříceniny", visited: 1, total: 1 });
});
