import { expect, test } from "vitest";
import type { CatalogPlace, StoredVisit } from "../src/catalog/types";
import { passportPages } from "../src/diary/passport";

const place = (id: string, region: string, name: string): CatalogPlace => ({
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
    latitude: 49.7,
    longitude: 16.8,
    address: null,
    municipality: "Obec",
    district: "Okres",
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
});

const visit = (id: string, placeId: string): StoredVisit => ({
  id,
  place_id: placeId,
  visited_at: "2026-08-09",
  rating: null,
  people: [],
  note: null,
  created_at: "2026-08-09T10:00:00+02:00",
  updated_at: "2026-08-09T10:00:00+02:00",
  deleted_at: null,
});

test("pas seskupí otisky podle kraje, jedno místo jednou", () => {
  const a = place("a", "Olomoucký kraj", "Bouzov");
  const b = place("b", "Olomoucký kraj", "Šternberk");
  const pages = passportPages([a, b], [visit("v1", "a"), visit("v2", "a"), visit("v3", "b")]);
  const olk = pages.find((page) => page.region.id === "OLK");
  expect(olk?.stamps).toHaveLength(2);
  expect(olk?.stamps.map((stamp) => stamp.name).sort()).toEqual(["Bouzov", "Šternberk"]);
  expect(olk?.total).toBe(2);
});
