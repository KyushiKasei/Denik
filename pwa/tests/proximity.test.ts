import { expect, test } from "vitest";
import { nearestPlaceHere } from "../src/geo/proximity";
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

test("nejbližší místo do 300 m", () => {
  const here = { latitude: 49.704, longitude: 16.891 };
  const close = place("1", "Bouzov", 49.7041, 16.8911);
  const far = place("2", "Daleko", 49.8, 17.0);
  const hit = nearestPlaceHere([far, close], here, 0.3);
  expect(hit?.place.name).toBe("Bouzov");
  expect(hit?.km ?? 1).toBeLessThan(0.05);
});

test("mimo práh nic nenabídne", () => {
  const here = { latitude: 49.704, longitude: 16.891 };
  const far = place("2", "Daleko", 49.8, 17.0);
  expect(nearestPlaceHere([far], here, 0.3)).toBeNull();
});
