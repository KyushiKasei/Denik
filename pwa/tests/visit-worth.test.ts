import { expect, test } from "vitest";
import type { CatalogPlace } from "../src/catalog/types";
import {
  isWeakStub,
  isWorthVisiting,
  loadWorthFilter,
  parseWorthParam,
  saveWorthFilter,
  visitScore,
} from "../src/catalog/visitWorth";

const place = (id: string, patch: Partial<CatalogPlace> = {}): CatalogPlace => ({
  id,
  name: id,
  short_name: null,
  alternative_names: [],
  types: ["CASTLE"],
  condition: "UNKNOWN",
  visitability: "UNKNOWN",
  short_description: null,
  heritage_status: "UNKNOWN",
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
  ...patch,
});

test("parseWorthParam čte all/visit z URL", () => {
  expect(parseWorthParam("all")).toBe(false);
  expect(parseWorthParam("ALL")).toBe(false);
  expect(parseWorthParam("0")).toBe(false);
  expect(parseWorthParam("false")).toBe(false);
  expect(parseWorthParam("visit")).toBe(true);
  expect(parseWorthParam("1")).toBe(true);
  expect(parseWorthParam("true")).toBe(true);
  expect(parseWorthParam(null)).toBeNull();
  expect(parseWorthParam("nope")).toBeNull();
});

test("výchozí pohled Za návštěvu se uloží do localStorage", () => {
  expect(loadWorthFilter()).toBe(true);
  saveWorthFilter(false);
  expect(loadWorthFilter()).toBe(false);
  saveWorthFilter(true);
  expect(loadWorthFilter()).toBe(true);
});

test("fotogenická zřícenina s volným přístupem stojí za návštěvu", () => {
  const trosky = place("trosky", {
    types: ["RUIN"],
    condition: "RUIN",
    visitability: "FREE_ACCESS",
    image: { thumbnail_url: "https://example.test/t.jpg", original_url: null, attribution: null, license: null, license_url: null },
  });
  expect(isWorthVisiting(trosky)).toBe(true);
  expect(visitScore(trosky)).toBeGreaterThan(visitScore(place("tráva")));
});

test("zaniklý hrad bez fota je pleva", () => {
  const grass = place("tráva", { condition: "EXTINCT", visitability: "EXTINCT" });
  expect(isWorthVisiting(grass)).toBe(false);
  expect(isWorthVisiting(place("val", { condition: "REMAINS", visitability: "FREE_ACCESS" }))).toBe(false);
});

test("NKP bez fota pořád projde", () => {
  const nkp = place("nkp", { heritage_status: "NKP", visitability: "UNKNOWN", condition: "UNKNOWN" });
  expect(isWorthVisiting(nkp)).toBe(true);
  expect(isWeakStub(nkp)).toBe(false);
});

test("soukromé a slabý stub schová", () => {
  expect(isWorthVisiting(place("priv", { condition: "PRESERVED", visitability: "PRIVATE" }))).toBe(false);
  expect(isWeakStub(place("stub"))).toBe(true);
  expect(isWorthVisiting(place("stub"))).toBe(false);
});

test("zachovalý s oficiálním webem má vyšší skóre než zřícenina", () => {
  const castle = place("hrad", {
    condition: "PRESERVED",
    visitability: "REGULAR",
    heritage_status: "NKP",
    links: {
      official: "https://example.test",
      wikipedia: "https://cs.wikipedia.org/wiki/X",
      wikidata: null,
      heritage_catalog: null,
      opening_hours: null,
      tickets: null,
    },
  });
  const ruin = place("zřícenina", { types: ["RUIN"], condition: "RUIN", visitability: "FREE_ACCESS" });
  expect(visitScore(castle)).toBeGreaterThan(visitScore(ruin));
});
