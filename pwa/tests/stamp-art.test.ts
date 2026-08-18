import { expect, test } from "vitest";
import type { CatalogPlace } from "../src/catalog/types";
import { stampArtForPlace, stampKindFromTypes, waxColorForRegion } from "../src/diary/stampArt";

const place: CatalogPlace = {
  id: "p1",
  name: "Bouzov",
  short_name: null,
  alternative_names: [],
  types: ["CASTLE", "CHATEAU"],
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

test("hrad má přednost před zámkem, zřícenina před hradem", () => {
  expect(stampKindFromTypes(["CASTLE", "CHATEAU"])).toBe("castle");
  expect(stampKindFromTypes(["CASTLE", "RUIN"])).toBe("ruin");
});

test("vosk podle kraje", () => {
  expect(waxColorForRegion("Olomoucký kraj")).toBe("#2e5a4a");
  expect(waxColorForRegion("Atlantis")).toBe("#3d5a40");
  expect(stampArtForPlace(place).kind).toBe("castle");
});
