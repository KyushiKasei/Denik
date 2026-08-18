import { expect, test } from "vitest";
import { downsampleTrack, parseGpxTrack, placesAlongTrack, GPX_MAX_POINTS } from "../src/geo/gpx";
import { MAX_NEARBY_HITS } from "../src/geo/nearby";
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

test("parseGpxTrack čte trkpt", () => {
  const xml = `<?xml version="1.0"?>
<gpx><trk><name>Výlet</name><trkseg>
<trkpt lat="49.704" lon="16.891"></trkpt>
<trkpt lat="49.705" lon="16.892"></trkpt>
</trkseg></trk></gpx>`;
  expect(parseGpxTrack(xml)).toEqual([
    { latitude: 49.704, longitude: 16.891 },
    { latitude: 49.705, longitude: 16.892 },
  ]);
});

test("parseGpxTrack bez bodů hodí chybu", () => {
  expect(() => parseGpxTrack(`<gpx><name>Prázdné</name></gpx>`)).toThrow(/souřadnice/);
});

test("místa do 400 m od stopy, vzdálená ne", () => {
  const track = [
    { latitude: 49.704, longitude: 16.891 },
    { latitude: 49.705, longitude: 16.892 },
  ];
  const along = place("1", "U trasy", 49.7042, 16.8912);
  const far = place("2", "Daleko", 50.08, 14.44);
  expect(placesAlongTrack([along, far], track).map((hit) => hit.place.id)).toEqual(["1"]);
});

test("placesAlongTrack ořízne na MAX_NEARBY_HITS", () => {
  const track = [{ latitude: 49.704, longitude: 16.891 }];
  const many = Array.from({ length: MAX_NEARBY_HITS + 5 }, (_, index) =>
    place(String(index), `Místo ${index}`, 49.704, 16.891),
  );
  expect(placesAlongTrack(many, track)).toHaveLength(MAX_NEARBY_HITS);
});

test("downsampleTrack nechá první i poslední bod", () => {
  const points = Array.from({ length: 10 }, (_, i) => ({ latitude: 50, longitude: 14 + i * 0.01 }));
  const down = downsampleTrack(points, 4);
  expect(down[0]).toEqual(points[0]);
  expect(down[down.length - 1]).toEqual(points[points.length - 1]);
  expect(down.length).toBeLessThanOrEqual(5);
});

test("hustá GPX se ořízne během čtení", () => {
  const pts = Array.from({ length: 2000 }, (_, i) => `<trkpt lat="49.${String(i).padStart(6, "0")}" lon="16.891"></trkpt>`).join("");
  const track = parseGpxTrack(`<gpx><trk><trkseg>${pts}</trkseg></trk></gpx>`);
  expect(track.length).toBeLessThanOrEqual(GPX_MAX_POINTS + 1);
  expect(track[0]?.latitude).toBeCloseTo(49, 0);
});
