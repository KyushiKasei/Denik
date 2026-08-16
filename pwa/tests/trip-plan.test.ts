import { expect, test } from "vitest";
import type { CatalogPlace } from "../src/catalog/types";
import { consecutiveStopKm, orderedStops, tripAirKm } from "../src/diary/tripPlan";
import type { StoredTrip } from "../src/diary/types";

const bouzov: CatalogPlace = {
  id: "0198f23a-5e5e-7b31-a8be-8c99507a2138",
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
    latitude: 49.704,
    longitude: 16.891,
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

const karlstejn: CatalogPlace = {
  ...bouzov,
  id: "0198f23a-5e5e-7b31-a8be-8c99507a2140",
  name: "Karlštejn",
  location: { ...bouzov.location, latitude: 49.939, longitude: 14.188, municipality: "Karlštejn" },
};

test("vzdušná km mezi sousedními zastávkami", () => {
  const trip: StoredTrip = {
    id: "0198f93b-618d-762f-a589-ccf375139dd8",
    name: "Test",
    planned_on: null,
    origin: null,
    notes: null,
    stops: [
      { place_id: karlstejn.id, sort_order: 1, note: null },
      { place_id: bouzov.id, sort_order: 0, note: null },
    ],
    created_at: "2026-08-16T10:00:00+02:00",
    updated_at: "2026-08-16T10:00:00+02:00",
    deleted_at: null,
  };
  const places = new Map([
    [bouzov.id, bouzov],
    [karlstejn.id, karlstejn],
  ]);
  const stops = orderedStops(trip);
  expect(stops[0]?.place_id).toBe(bouzov.id);
  const gaps = consecutiveStopKm(stops, places);
  expect(gaps).toHaveLength(1);
  expect(gaps[0]).toBeGreaterThan(150);
  expect(gaps[0]).toBeLessThan(250);
  expect(tripAirKm(trip, places)).toBe(gaps[0]);
});
