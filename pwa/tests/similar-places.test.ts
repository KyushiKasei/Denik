import { expect, test } from "vitest";
import { similarPlaces } from "../src/diary/similarPlaces";
import type { CatalogPlace } from "../src/catalog/types";

function place(id: string, name: string, extra: Partial<CatalogPlace> = {}): CatalogPlace {
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
      latitude: 49.7,
      longitude: 16.8,
      address: null,
      municipality: name,
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
    architectural_style: "gotika",
    inception_year: 1310,
    ...extra,
  };
}

test("podobná místa řadí stejný typ, sloh a kraj, vynechá navštívené", () => {
  const source = place("1", "Bouzov");
  const twin = place("2", "Šternberk");
  const otherRegion = place("3", "Karlštejn", {
    location: {
      ...source.location,
      region: "Středočeský kraj",
      municipality: "Karlštejn",
      district: "Beroun",
    },
  });
  const zoo = place("4", "Zoo", {
    types: ["ZOO"],
    architectural_style: null,
    inception_year: null,
    heritage_status: "NONE",
    location: {
      ...source.location,
      region: "Hlavní město Praha",
      municipality: "Praha",
      district: "Praha",
    },
  });
  const visited = place("5", "Bečov");
  const found = similarPlaces(source, [source, twin, otherRegion, zoo, visited], [{ place_id: "5", deleted_at: null }]);
  expect(found.map((row) => row.id)).toEqual(["2", "3"]);
});

test("podobná místa vyžadují společný typ, nestačí stejný kraj", () => {
  const source = place("1", "Karlštejn");
  const hunting = place("2", "Bon Repos", {
    types: ["PALACE"],
    architectural_style: null,
    inception_year: null,
    heritage_status: "NONE",
  });
  expect(similarPlaces(source, [source, hunting], []).map((row) => row.id)).toEqual([]);
});
