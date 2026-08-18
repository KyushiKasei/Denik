import { expect, test } from "vitest";
import type { CatalogPlace, StoredVisit } from "../src/catalog/types";
import {
  atlasActivePlaceId,
  atlasPlaces,
  atlasPlacesAt,
  atlasTimeCaption,
  atlasTimeline,
  atlasYears,
  lastIndexForYear,
  parseUntilParam,
  timelineIndexForUntil,
} from "../src/diary/atlas";

const place = (
  id: string,
  name: string,
  opts?: { lat?: number | null; lon?: number | null; region?: string },
): CatalogPlace => ({
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
    latitude: opts?.lat === undefined ? 49.7 : opts.lat,
    longitude: opts?.lon === undefined ? 16.8 : opts.lon,
    address: null,
    municipality: "Obec",
    district: "Okres",
    region: opts?.region ?? "Olomoucký kraj",
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
});

const visit = (
  id: string,
  placeId: string,
  visitedAt: string | null,
  createdAt = "2026-01-01T10:00:00+01:00",
): StoredVisit => ({
  id,
  place_id: placeId,
  visited_at: visitedAt,
  rating: null,
  people: [],
  note: null,
  created_at: createdAt,
  updated_at: createdAt,
  deleted_at: null,
});

const filters = {
  query: "",
  type: "" as const,
  region: "",
  district: "",
  journal: "" as const,
};

test("atlasTimeline řadí datum vzestupně, bez data nakonec, místo bez GPS vynechá", () => {
  const bouzov = place("a", "Bouzov");
  const krumlov = place("b", "Český Krumlov", { lat: 48.8, lon: 14.3 });
  const ghost = place("c", "Bez GPS", { lat: null, lon: null });
  const timeline = atlasTimeline(
    [
      visit("v2", "a", "2024-06-15", "2024-06-15T12:00:00+02:00"),
      visit("v1", "b", "2022-07-09", "2022-07-09T12:00:00+02:00"),
      visit("v3", "a", "2025-07-12", "2025-07-12T12:00:00+02:00"),
      visit("v4", "a", null, "2026-01-02T12:00:00+01:00"),
      visit("v5", "c", "2023-01-01"),
    ],
    [bouzov, krumlov, ghost],
  );
  expect(timeline.map((event) => event.visitId)).toEqual(["v1", "v2", "v3", "v4"]);
  expect(timeline[3].visitedAt).toBeNull();
});

test("until ukáže stav k datu, duplicitní místo jednou, want jen dnes", () => {
  const bouzov = place("a", "Bouzov");
  const krumlov = place("b", "Český Krumlov", { lat: 48.8, lon: 14.3 });
  const lednice = place("c", "Lednice", { lat: 48.8, lon: 16.8 });
  const visits = [
    visit("v1", "b", "2022-07-09"),
    visit("v2", "a", "2024-06-15"),
    visit("v3", "a", "2025-07-12"),
  ];
  const timeline = atlasTimeline(visits, [bouzov, krumlov, lednice]);
  const rows = atlasPlaces([bouzov, krumlov, lednice], filters, {
    visitedIds: new Set(["a", "b"]),
    wantIds: new Set(["c"]),
  });
  expect(rows.map((row) => row.place.name).sort((a, b) => a.localeCompare(b, "cs"))).toEqual([
    "Bouzov",
    "Český Krumlov",
    "Lednice",
  ]);

  expect(parseUntilParam("2024-12-31")).toBe("2024-12-31");
  expect(parseUntilParam("nope")).toBeNull();
  expect(timelineIndexForUntil(timeline, null)).toBe("today");
  expect(timelineIndexForUntil(timeline, "2020-01-01")).toBe(-1);
  expect(timelineIndexForUntil(timeline, "2024-12-31")).toBe(1);

  const at2024 = atlasPlacesAt(rows, timeline, 1);
  expect(at2024.map((row) => row.place.name).sort((a, b) => a.localeCompare(b, "cs"))).toEqual([
    "Bouzov",
    "Český Krumlov",
  ]);
  expect(at2024.every((row) => row.kind === "visited")).toBe(true);

  const today = atlasPlacesAt(rows, timeline, "today");
  expect(today.some((row) => row.place.id === "c" && row.kind === "want")).toBe(true);

  expect(atlasPlacesAt(rows, timeline, -1)).toEqual([]);
  expect(atlasActivePlaceId(timeline, 1)).toBe("a");
  expect(atlasActivePlaceId(timeline, "today")).toBeNull();
  expect(atlasYears(timeline)).toEqual([2022, 2024, 2025]);
  expect(lastIndexForYear(timeline, 2024)).toBe(1);
  expect(atlasTimeCaption(timeline, 0)).toBe("9. 7. 2022 · Český Krumlov");
  expect(atlasTimeCaption(timeline, "today")).toBe("Dnes");
});
