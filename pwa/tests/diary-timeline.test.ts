import { expect, test } from "vitest";
import type { CatalogPlace, PlaceNameSnapshot, StoredPlaceState, StoredVisit } from "../src/catalog/types";
import {
  diaryHeaderStats,
  formatDiaryStatsLine,
  formatStars,
  formatVisitDate,
  listFavoriteRows,
  listVisitRows,
  listWantToVisitRows,
  shortNote,
  sortVisitsNewestFirst,
} from "../src/diary/timeline";

const place: CatalogPlace = {
  id: "place-a",
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

function visit(partial: Partial<StoredVisit> & Pick<StoredVisit, "id" | "place_id">): StoredVisit {
  return {
    visited_at: "2026-08-09",
    rating: 4,
    people: [],
    note: null,
    created_at: "2026-08-09T10:00:00+02:00",
    updated_at: "2026-08-09T10:00:00+02:00",
    deleted_at: null,
    ...partial,
  };
}

test("sortVisitsNewestFirst řadí od nejnovější a vynechá smazané", () => {
  const older = visit({ id: "1", place_id: "a", visited_at: "2026-08-01" });
  const newer = visit({ id: "2", place_id: "a", visited_at: "2026-08-12" });
  const deleted = visit({ id: "3", place_id: "a", visited_at: "2026-08-20", deleted_at: "2026-08-21T00:00:00+02:00" });
  const sameDayLater = visit({
    id: "4",
    place_id: "b",
    visited_at: "2026-08-12",
    created_at: "2026-08-12T18:00:00+02:00",
  });
  expect(sortVisitsNewestFirst([older, deleted, newer, sameDayLater]).map((row) => row.id)).toEqual(["4", "2", "1"]);
});

test("formatVisitDate a hvězdy a zkrácená poznámka", () => {
  expect(formatVisitDate("2026-08-09")).toBe("9. 8. 2026");
  expect(formatVisitDate(null)).toBe("bez data");
  expect(formatStars(3)).toBe("★★★☆☆");
  expect(formatStars(null)).toBe("—");
  expect(shortNote("  krátká  ")).toBe("krátká");
  expect(shortNote("x".repeat(20), 10)).toBe(`${"x".repeat(9)}…`);
});

test("listVisitRows vezme název z katalogu nebo ze snapshotu", () => {
  const snapshot: PlaceNameSnapshot = {
    place_id: "gone",
    name: "Starý hrad",
    municipality: "Jinde",
    updated_at: "2026-08-01T00:00:00+02:00",
  };
  const rows = listVisitRows(
    [
      visit({ id: "v1", place_id: "place-a", visited_at: "2026-08-10", note: "Pěkné ráno." }),
      visit({ id: "v2", place_id: "gone", visited_at: "2026-08-08" }),
    ],
    new Map([[place.id, place]]),
    new Map([[snapshot.place_id, snapshot]]),
  );
  expect(rows[0]?.name).toBe("Bouzov");
  expect(rows[0]?.missingFromCatalog).toBe(false);
  expect(rows[0]?.notePreview).toBe("Pěkné ráno.");
  expect(rows[1]?.name).toBe("Starý hrad");
  expect(rows[1]?.missingFromCatalog).toBe(true);
  expect(rows[1]?.municipality).toBe("Jinde");
});

test("wishlist a oblíbené skrývají smazané stavy a řadí podle názvu", () => {
  const other: CatalogPlace = { ...place, id: "place-b", name: "Bečov" };
  const states: StoredPlaceState[] = [
    {
      place_id: "place-b",
      want_to_visit: true,
      favorite: true,
      personal_note: null,
      updated_at: "2026-08-09T10:00:00+02:00",
      deleted_at: null,
    },
    {
      place_id: "place-a",
      want_to_visit: true,
      favorite: false,
      personal_note: null,
      updated_at: "2026-08-09T10:00:00+02:00",
      deleted_at: null,
    },
    {
      place_id: "gone",
      want_to_visit: false,
      favorite: true,
      personal_note: null,
      updated_at: "2026-08-09T10:00:00+02:00",
      deleted_at: null,
    },
    {
      place_id: "deleted",
      want_to_visit: true,
      favorite: true,
      personal_note: null,
      updated_at: "2026-08-09T10:00:00+02:00",
      deleted_at: "2026-08-10T00:00:00+02:00",
    },
  ];
  const places = new Map([
    [place.id, place],
    [other.id, other],
  ]);
  const snaps = new Map<string, PlaceNameSnapshot>([
    ["gone", { place_id: "gone", name: "Zmizelé", municipality: null, updated_at: "2026-08-01T00:00:00+02:00" }],
  ]);
  expect(listWantToVisitRows(states, places, snaps).map((row) => row.name)).toEqual(["Bečov", "Bouzov"]);
  const favs = listFavoriteRows(states, places, snaps);
  expect(favs.map((row) => row.name)).toEqual(["Bečov", "Zmizelé"]);
  expect(favs[1]?.missingFromCatalog).toBe(true);
});

test("header statistika počítá návštěvy, unikátní místa a oblíbené", () => {
  const stats = diaryHeaderStats(
    [
      visit({ id: "1", place_id: "a" }),
      visit({ id: "2", place_id: "a", visited_at: "2026-08-11" }),
      visit({ id: "3", place_id: "b" }),
      visit({ id: "4", place_id: "c", deleted_at: "2026-08-12T00:00:00+02:00" }),
    ],
    [
      {
        place_id: "a",
        want_to_visit: false,
        favorite: true,
        personal_note: null,
        updated_at: "2026-08-09T10:00:00+02:00",
        deleted_at: null,
      },
      {
        place_id: "x",
        want_to_visit: false,
        favorite: true,
        personal_note: null,
        updated_at: "2026-08-09T10:00:00+02:00",
        deleted_at: "2026-08-10T00:00:00+02:00",
      },
    ],
  );
  expect(stats).toEqual({ visitCount: 3, uniquePlaceCount: 2, favoriteCount: 1 });
  expect(formatDiaryStatsLine(stats)).toBe("3 návštěvy · 2 místa · 1 oblíbené");
});
