import { expect, test } from "vitest";
import { parseExtraParam, parseMoodParam, placeMatchesExtra, placeMatchesMood } from "../src/catalog/moods";
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

test("nálada zřícenin bere RUIN typ i stav", () => {
  const ruin: CatalogPlace = { ...base, id: "2", types: ["RUIN"], condition: "RUIN" };
  expect(placeMatchesMood(ruin, "ruins")).toBe(true);
  expect(placeMatchesMood({ ...base, condition: "RUIN" }, "ruins")).toBe(true);
  expect(placeMatchesMood(base, "ruins")).toBe(false);
});

test("nálada interiérů vynechá zříceninu a volný přístup", () => {
  const free: CatalogPlace = { ...base, id: "3", visitability: "FREE_ACCESS" };
  expect(placeMatchesMood(base, "indoors")).toBe(true);
  expect(placeMatchesMood(free, "indoors")).toBe(false);
  expect(placeMatchesMood({ ...base, types: ["RUIN"] }, "indoors")).toBe(false);
  expect(placeMatchesMood({ ...base, condition: "RUIN" }, "indoors")).toBe(false);
});

test("UNESCO / NKP a venku s dětmi", () => {
  expect(placeMatchesMood(base, "heritage")).toBe(true);
  expect(placeMatchesMood({ ...base, heritage_status: "NONE" }, "heritage")).toBe(false);
  expect(placeMatchesMood({ ...base, unesco: true, heritage_status: "NONE" }, "heritage")).toBe(true);
  expect(placeMatchesMood({ ...base, types: ["LOOKOUT_TOWER"] }, "lookouts")).toBe(true);
  expect(placeMatchesMood(base, "lookouts")).toBe(false);
});

test("parseMoodParam ignoruje neznámé", () => {
  expect(parseMoodParam("ruins")).toBe("ruins");
  expect(parseMoodParam("RUINS")).toBe("ruins");
  expect(parseMoodParam("nope")).toBe("");
});

test("extra filtr psa, zdarma a zázemí", () => {
  const dog: CatalogPlace = { ...base, dogs: "leashed", fee: "no", amenities: ["toilets", "cafe"] };
  expect(placeMatchesExtra(dog, "dogs")).toBe(true);
  expect(placeMatchesExtra(base, "dogs")).toBe(false);
  expect(placeMatchesExtra(dog, "free")).toBe(true);
  expect(placeMatchesExtra(dog, "toilets")).toBe(true);
  expect(placeMatchesExtra(dog, "playground")).toBe(false);
  expect(parseExtraParam("cafe")).toBe("cafe");
  expect(parseExtraParam("CAFE")).toBe("cafe");
  expect(parseExtraParam("wifi")).toBe("");
});
