import { expect, test } from "vitest";
import type { CatalogPlace } from "../src/catalog/types";
import { buildTripGpx, buildTripIcs, googleMapsMultiStopUrl } from "../src/diary/tripExport";
import type { StoredTrip } from "../src/diary/types";

const place: CatalogPlace = {
  id: "a",
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

const trip: StoredTrip = {
  id: "0198f93b-618d-762f-a589-ccf375139dd8",
  name: "Olomoucko",
  planned_on: "2026-08-20",
  origin: { latitude: 49.59, longitude: 17.25, label: "Olomouc" },
  notes: null,
  status: "planned",
  stops: [{ place_id: "a", sort_order: 0, note: null }],
  created_at: "2026-08-16T10:00:00+02:00",
  updated_at: "2026-08-16T10:00:00+02:00",
  deleted_at: null,
};

test("ICS obsahuje den a název", () => {
  const ics = buildTripIcs(trip, new Map([[place.id, place]]));
  expect(ics).toContain("DTSTART;VALUE=DATE:20260820");
  expect(ics).toContain("SUMMARY:Olomoucko");
  expect(ics).toContain("Bouzov");
});

test("GPX má waypoint", () => {
  const gpx = buildTripGpx(trip, new Map([[place.id, place]]));
  expect(gpx).toContain('lat="49.704"');
  expect(gpx).toContain("Bouzov");
});

test("Google Maps URL má origin i cíl", () => {
  const url = googleMapsMultiStopUrl(trip.origin, [place]);
  expect(url).toContain("origin=49.59%2C17.25");
  expect(url).toContain("destination=49.704%2C16.891");
});
