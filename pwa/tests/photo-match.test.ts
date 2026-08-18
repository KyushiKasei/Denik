import { expect, test } from "vitest";
import { parseJpegExif } from "../src/diary/exif";
import { matchExifToPlace } from "../src/diary/photoMatch";
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

test("EXIF GPS přiřadí nejbližší místo do 500 m", () => {
  const bouzov = place("1", "Bouzov", 49.704, 16.891);
  const prague = place("2", "Praha", 50.087, 14.421);
  const hit = matchExifToPlace([prague, bouzov], { latitude: 49.7042, longitude: 16.8912, takenAt: "2026-08-18" });
  expect(hit?.place.name).toBe("Bouzov");
  expect(hit?.km ?? 1).toBeLessThan(0.05);
});

test("bez GPS se místo nehádá", () => {
  const bouzov = place("1", "Bouzov", 49.704, 16.891);
  expect(matchExifToPlace([bouzov], { latitude: null, longitude: null, takenAt: "2026-08-18" })).toBeNull();
});

test("ne-JPEG vrátí prázdný EXIF", () => {
  const buffer = new TextEncoder().encode("not a jpeg").buffer;
  expect(parseJpegExif(buffer)).toEqual({ latitude: null, longitude: null, takenAt: null });
});
