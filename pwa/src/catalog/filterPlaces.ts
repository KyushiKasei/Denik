import type { CatalogPlace, ConditionCode, PlaceTypeCode, VisitabilityCode } from "./types";
import { CONDITION_OPTIONS, hasGps, HERITAGE_OPTIONS, PLACE_TYPE_OPTIONS, VISITABILITY_FILTER_GROUPS, VISITABILITY_OPTIONS, visitabilityMatches } from "./labels";
import { appliedSearchQuery, fold } from "../text/fold";
import { isInOpenSeason, isSeasonallyLikelyClosed, parseHoursParam, parseOpenMonthParam, placeOpenState, type HoursFilter } from "./openingHours";
import { isWorthVisiting, loadWorthFilter, parseWorthParam, visitScore } from "./visitWorth";
import { parseExtraParam, placeMatchesExtra, type PlaceExtraFilter } from "./moods";
import { isRuin, placeMatchesType } from "./ruins";

export type VisitabilityFilter = VisitabilityCode | "PUBLIC" | "NOT_PUBLIC" | "";
export type JournalFilter = "" | "visited" | "not_visited" | "want_to_visit" | "favorite";
export type UnescoFilter = "" | "yes" | "no";
export type GpsFilter = "" | "with" | "without";
export type PlaceSort = "name" | "name_desc" | "region" | "worth";

export interface PlaceFilters {
  query: string;
  type: PlaceTypeCode | "";
  region: string;
  district: string;
  visitability?: VisitabilityFilter;
  journal: JournalFilter;
  unesco?: UnescoFilter;
  heritage?: string;
  condition?: ConditionCode | "";
  gps?: GpsFilter;
  worth?: boolean;
  sort?: PlaceSort;
  hours?: HoursFilter;
  openMonth?: number | "";
  extra?: PlaceExtraFilter;
  lost?: boolean;
  style?: string;
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
  condition: "",
  gps: "",
  worth: true,
  sort: "name",
  hours: "",
  openMonth: "",
  extra: "",
  lost: false,
  style: "",
};

export const PLACE_SORT_OPTIONS: Array<{ code: PlaceSort; name_cs: string }> = [
  { code: "name", name_cs: "Název A–Z" },
  { code: "name_desc", name_cs: "Název Z–A" },
  { code: "region", name_cs: "Kraj" },
  { code: "worth", name_cs: "Zajímavost" },
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
  if (raw === "name_desc" || raw === "region" || raw === "worth") {
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
  if (sort === "worth") {
    copy.sort((a, b) => visitScore(b) - visitScore(a) || a.name.localeCompare(b.name, "cs"));
    return copy;
  }
  copy.sort((a, b) => a.name.localeCompare(b.name, "cs"));
  return copy;
}

export function uniqueSorted(values: Array<string | null | undefined>): string[] {
  const set = new Set<string>();
  for (const value of values) {
    if (!value) {
      continue;
    }
    for (const part of splitLocationParts(value)) {
      set.add(part);
    }
  }
  return [...set].sort((a, b) => a.localeCompare(b, "cs"));
}

export function splitLocationParts(raw: string): string[] {
  return raw
    .split(/[;,]/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function locationFieldMatches(raw: string | null | undefined, selected: string): boolean {
  if (!selected) {
    return true;
  }
  if (!raw) {
    return false;
  }
  if (raw === selected) {
    return true;
  }
  return splitLocationParts(raw).includes(selected);
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

export { parseHoursParam, parseOpenMonthParam, parseExtraParam };

export function parseConditionParam(raw: string | null): ConditionCode | "" {
  if (!raw) {
    return "";
  }
  return CONDITION_OPTIONS.some((item) => item.code === raw) ? (raw as ConditionCode) : "";
}

function knownVisitability(value: string): value is Exclude<VisitabilityFilter, ""> {
  return (
    VISITABILITY_FILTER_GROUPS.some((item) => item.code === value) ||
    VISITABILITY_OPTIONS.some((item) => item.code === value)
  );
}

export function filtersFromParams(params: URLSearchParams): PlaceFilters {
  const type = params.get("type") ?? "";
  const known = PLACE_TYPE_OPTIONS.some((item) => item.code === type);
  const visitabilityRaw = params.get("visitability") ?? "";
  return {
    query: params.get("q") ?? "",
    type: known ? (type as PlaceTypeCode) : "",
    region: params.get("region") ?? "",
    district: params.get("district") ?? "",
    visitability: knownVisitability(visitabilityRaw) ? visitabilityRaw : "",
    journal: parseJournalParam(params.get("journal")),
    unesco: parseUnescoParam(params.get("unesco")),
    heritage: parseHeritageParam(params.get("heritage")),
    condition: parseConditionParam(params.get("condition")),
    gps: parseGpsParam(params.get("gps")),
    worth: parseWorthParam(params.get("worth")) ?? loadWorthFilter(),
    sort: parseSortParam(params.get("sort")),
    hours: parseHoursParam(params.get("hours")),
    openMonth: parseOpenMonthParam(params.get("month")),
    extra: parseExtraParam(params.get("extra")),
    lost: params.get("lost") === "yes",
    style: params.get("style") ?? "",
  };
}

export function filterPlaces(
  places: CatalogPlace[],
  filters: PlaceFilters,
  diary?: DiaryFilterSets,
): CatalogPlace[] {
  const needle = fold(appliedSearchQuery(filters.query));
  const matched = places.filter((place) => {
      if (filters.type && !placeMatchesType(place, filters.type)) {
        return false;
      }
      if (filters.region && place.location.region !== filters.region) {
        return false;
      }
      if (filters.district && !locationFieldMatches(place.location.district, filters.district)) {
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
      if (filters.condition && place.condition !== filters.condition) {
        return false;
      }
      if (filters.worth && !filters.lost && !isWorthVisiting(place)) {
        return false;
      }
      if (filters.gps === "with" && !hasGps(place)) {
        return false;
      }
      if (filters.gps === "without" && hasGps(place)) {
        return false;
      }
      if (filters.hours === "open" && placeOpenState(place) !== "open") {
        return false;
      }
      if (filters.hours === "season" && !isInOpenSeason(place)) {
        return false;
      }
      if (filters.openMonth) {
        const at = new Date(new Date().getFullYear(), filters.openMonth - 1, 15, 12, 0, 0);
        if (isSeasonallyLikelyClosed(place, at)) {
          return false;
        }
      }
      if (filters.extra && !placeMatchesExtra(place, filters.extra)) {
        return false;
      }
      if (filters.lost && place.condition !== "EXTINCT" && place.condition !== "REMAINS") {
        return false;
      }
      if (filters.style && (place.architectural_style || "") !== filters.style) {
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
  condition: Record<string, number>;
  gps: Record<string, number>;
  worth: { visit: number; all: number };
  hours: Record<string, number>;
  extra: Record<string, number>;
  lost: { yes: number; all: number };
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
    if (isRuin(place) && !place.types.includes("RUIN")) {
      bump(types, "RUIN");
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
    const parts = splitLocationParts(place.location.district ?? "");
    if (parts.length === 0) {
      continue;
    }
    for (const part of parts) {
      bump(districts, part);
    }
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

  const conditionBase = filterPlaces(places, { ...filters, condition: "" }, diary);
  const condition: Record<string, number> = { "": conditionBase.length };
  for (const place of conditionBase) {
    bump(condition, place.condition);
  }

  const worthBase = filterPlaces(places, { ...filters, worth: false }, diary);
  const worth = {
    all: worthBase.length,
    visit: worthBase.filter(isWorthVisiting).length,
  };

  const hoursBase = filterPlaces(places, { ...filters, hours: "" }, diary);
  const hours: Record<string, number> = {
    "": hoursBase.length,
    open: filterPlaces(places, { ...filters, hours: "open" }, diary).length,
    season: filterPlaces(places, { ...filters, hours: "season" }, diary).length,
  };

  const extraBase = filterPlaces(places, { ...filters, extra: "" }, diary);
  const extra: Record<string, number> = {
    "": extraBase.length,
    dogs: filterPlaces(places, { ...filters, extra: "dogs" }, diary).length,
    free: filterPlaces(places, { ...filters, extra: "free" }, diary).length,
    toilets: filterPlaces(places, { ...filters, extra: "toilets" }, diary).length,
    cafe: filterPlaces(places, { ...filters, extra: "cafe" }, diary).length,
    playground: filterPlaces(places, { ...filters, extra: "playground" }, diary).length,
  };

  const lostBase = filterPlaces(places, { ...filters, lost: false, worth: false }, diary);
  const lost = {
    all: lostBase.length,
    yes: lostBase.filter((place) => place.condition === "EXTINCT" || place.condition === "REMAINS").length,
  };

  return { visitability, types, regions, districts, journal, unesco, heritage, condition, gps, worth, hours, extra, lost };
}
