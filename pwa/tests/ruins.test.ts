import { expect, test } from "vitest";
import { isRuin, placeMatchesType } from "../src/catalog/ruins";
import type { CatalogPlace } from "../src/catalog/types";

const base: CatalogPlace = {
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
    latitude: 49.7,
    longitude: 16.8,
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

test("isRuin je typ nebo stav, včetně zaniklého s typem RUIN", () => {
  expect(isRuin(base)).toBe(false);
  expect(isRuin({ ...base, types: ["RUIN"], condition: "UNKNOWN" })).toBe(true);
  expect(isRuin({ ...base, types: ["CASTLE"], condition: "RUIN" })).toBe(true);
  expect(isRuin({ ...base, types: ["RUIN"], condition: "EXTINCT" })).toBe(true);
});

test("placeMatchesType u RUIN používá isRuin", () => {
  const byCondition: CatalogPlace = { ...base, condition: "RUIN" };
  expect(placeMatchesType(byCondition, "RUIN")).toBe(true);
  expect(placeMatchesType(byCondition, "CASTLE")).toBe(true);
  expect(placeMatchesType(base, "RUIN")).toBe(false);
});
