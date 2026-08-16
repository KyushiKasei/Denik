import type { CatalogPlace, PlaceTypeCode, VisitabilityCode } from "./types";
import { hasGps, HERITAGE_OPTIONS, VISITABILITY_FILTER_GROUPS, visitabilityMatches } from "./labels";
import { fold } from "../text/fold";

export type VisitabilityFilter = VisitabilityCode | "PUBLIC" | "NOT_PUBLIC" | "";
export type JournalFilter = "" | "visited" | "not_visited" | "want_to_visit" | "favorite";
export type UnescoFilter = "" | "yes" | "no";
export type GpsFilter = "" | "with" | "without";
export type PlaceSort = "name" | "name_desc" | "region";

export interface PlaceFilters {
  query: string;
  type: PlaceTypeCode | "";
  region: string;
  district: string;
  visitability?: VisitabilityFilter;
  journal: JournalFilter;
  unesco?: UnescoFilter;
  heritage?: string;
  gps?: GpsFilter;
  sort?: PlaceSort;
}

export const EMPTY_FILTERS: PlaceFilters = {
  query: "",
  type: "",
  region: "",
  district: "",
  visitability: "",
  journal: "",
  unesco: "",
  heritage: "",
  gps: "",
  sort: "name",
};

export const PLACE_SORT_OPTIONS: Array<{ code: PlaceSort; name_cs: string }> = [
  { code: "name", name_cs: "Název A–Z" },
  { code: "name_desc", name_cs: "Název Z–A" },
  { code: "region", name_cs: "Kraj" },
];

const haystackCache = new WeakMap<CatalogPlace, string>();

export const JOURNAL_FILTER_VALUES: JournalFilter[] = ["visited", "not_visited", "want_to_visit", "favorite"];

export interface DiaryFilterSets {
  visitedIds: Set<string>;
  wantIds: Set<string>;
  favIds?: Set<string>;
}

function haystack(place: CatalogPlace): string {
  const cached = haystackCache.get(place);
  if (cached !== undefined) {
    return cached;
  }
  const value = fold(
    [
      place.name,
      place.short_name ?? "",
      ...place.alternative_names,
      place.location.municipality ?? "",
      place.location.district ?? "",
      place.location.region ?? "",
    ].join(" "),
  );
  haystackCache.set(place, value);
  return value;
}

export function primeHaystacks(places: CatalogPlace[]): void {
  for (const place of places) {
    haystack(place);
  }
}

export function parseSortParam(raw: string | null): PlaceSort {
  if (raw === "name_desc" || raw === "region") {
    return raw;
  }
  return "name";
}

function sortPlaces(places: CatalogPlace[], sort: PlaceSort): CatalogPlace[] {
  const copy = [...places];
  if (sort === "name_desc") {
    copy.sort((a, b) => b.name.localeCompare(a.name, "cs"));
    return copy;
  }
  if (sort === "region") {
    copy.sort(
      (a, b) =>
        (a.location.region ?? "").localeCompare(b.location.region ?? "", "cs") || a.name.localeCompare(b.name, "cs"),
    );
    return copy;
  }
  copy.sort((a, b) => a.name.localeCompare(b.name, "cs"));
  return copy;
}

export function uniqueSorted(values: Array<string | null | undefined>): string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value)))].sort((a, b) =>
    a.localeCompare(b, "cs"),
  );
}

export function parseJournalParam(raw: string | null): JournalFilter {
  return JOURNAL_FILTER_VALUES.includes(raw as JournalFilter) ? (raw as JournalFilter) : "";
}

export function parseUnescoParam(raw: string | null): UnescoFilter {
  return raw === "yes" || raw === "no" ? raw : "";
}

export function parseGpsParam(raw: string | null): GpsFilter {
  return raw === "with" || raw === "without" ? raw : "";
}

export function parseHeritageParam(raw: string | null): string {
  if (!raw) {
    return "";
  }
  return HERITAGE_OPTIONS.some((item) => item.code === raw) ? raw : "";
}

export function filterPlaces(
  places: CatalogPlace[],
  filters: PlaceFilters,
  diary?: DiaryFilterSets,
): CatalogPlace[] {
  const needle = fold(filters.query.trim());
  const matched = places.filter((place) => {
      if (filters.type && !place.types.includes(filters.type)) {
        return false;
      }
      if (filters.region && place.location.region !== filters.region) {
        return false;
      }
      if (filters.district && place.location.district !== filters.district) {
        return false;
      }
      if (filters.visitability && !visitabilityMatches(place.visitability, filters.visitability)) {
        return false;
      }
      if (filters.unesco === "yes" && !place.unesco) {
        return false;
      }
      if (filters.unesco === "no" && place.unesco) {
        return false;
      }
      if (filters.heritage && place.heritage_status !== filters.heritage) {
        return false;
      }
      if (filters.gps === "with" && !hasGps(place)) {
        return false;
      }
      if (filters.gps === "without" && hasGps(place)) {
        return false;
      }
      if (filters.journal === "visited" && !diary?.visitedIds.has(place.id)) {
        return false;
      }
      if (filters.journal === "not_visited" && diary?.visitedIds.has(place.id)) {
        return false;
      }
      if (filters.journal === "want_to_visit" && !diary?.wantIds.has(place.id)) {
        return false;
      }
      if (filters.journal === "favorite" && !diary?.favIds?.has(place.id)) {
        return false;
      }
      if (needle && !haystack(place).includes(needle)) {
        return false;
      }
      return true;
    });
  return sortPlaces(matched, filters.sort ?? "name");
}

export function withCount(label: string, count: number | undefined): string {
  return `${label} (${count ?? 0})`;
}

function bump(counts: Record<string, number>, key: string | null | undefined, n = 1): void {
  if (!key) {
    return;
  }
  counts[key] = (counts[key] ?? 0) + n;
}

export interface FacetCounts {
  visitability: Record<string, number>;
  types: Record<string, number>;
  regions: Record<string, number>;
  districts: Record<string, number>;
  journal: Record<string, number>;
  unesco: Record<string, number>;
  heritage: Record<string, number>;
  gps: Record<string, number>;
}

export function facetCounts(
  places: CatalogPlace[],
  filters: PlaceFilters,
  diary?: DiaryFilterSets,
): FacetCounts {
  const visitBase = filterPlaces(places, { ...filters, visitability: "" }, diary);
  const visitability: Record<string, number> = { "": visitBase.length };
  for (const place of visitBase) {
    bump(visitability, place.visitability);
  }
  for (const group of VISITABILITY_FILTER_GROUPS) {
    visitability[group.code] = group.codes.reduce((sum, code) => sum + (visitability[code] ?? 0), 0);
  }

  const typeBase = filterPlaces(places, { ...filters, type: "" }, diary);
  const types: Record<string, number> = { "": typeBase.length };
  for (const place of typeBase) {
    for (const code of place.types) {
      bump(types, code);
    }
  }

  const regionBase = filterPlaces(places, { ...filters, region: "" }, diary);
  const regions: Record<string, number> = { "": regionBase.length };
  for (const place of regionBase) {
    bump(regions, place.location.region);
  }

  const districtBase = filterPlaces(places, { ...filters, district: "" }, diary);
  const districts: Record<string, number> = { "": districtBase.length };
  for (const place of districtBase) {
    bump(districts, place.location.district);
  }

  const journalBase = filterPlaces(places, { ...filters, journal: "" }, diary);
  const journal: Record<string, number> = {
    "": journalBase.length,
    visited: filterPlaces(places, { ...filters, journal: "visited" }, diary).length,
    not_visited: filterPlaces(places, { ...filters, journal: "not_visited" }, diary).length,
    want_to_visit: filterPlaces(places, { ...filters, journal: "want_to_visit" }, diary).length,
    favorite: filterPlaces(places, { ...filters, journal: "favorite" }, diary).length,
  };

  const unescoBase = filterPlaces(places, { ...filters, unesco: "" }, diary);
  const unesco: Record<string, number> = {
    "": unescoBase.length,
    yes: unescoBase.filter((place) => place.unesco).length,
    no: unescoBase.filter((place) => !place.unesco).length,
  };

  const heritageBase = filterPlaces(places, { ...filters, heritage: "" }, diary);
  const heritage: Record<string, number> = { "": heritageBase.length };
  for (const place of heritageBase) {
    bump(heritage, place.heritage_status);
  }

  const gpsBase = filterPlaces(places, { ...filters, gps: "" }, diary);
  const gps: Record<string, number> = {
    "": gpsBase.length,
    with: gpsBase.filter(hasGps).length,
    without: gpsBase.filter((place) => !hasGps(place)).length,
  };

  return { visitability, types, regions, districts, journal, unesco, heritage, gps };
}
