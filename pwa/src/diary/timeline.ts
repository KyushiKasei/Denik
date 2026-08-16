import type { CatalogPlace, PlaceNameSnapshot, StoredPlaceState, StoredVisit } from "../catalog/types";

export type DiarySection = "visits" | "want" | "fav" | "trips";

export interface DiaryPlaceRef {
  place_id: string;
  name: string;
  municipality: string | null;
  missingFromCatalog: boolean;
}

export interface DiaryVisitRow extends DiaryPlaceRef {
  visit: StoredVisit;
  dateLabel: string;
  stars: string;
  notePreview: string | null;
}

export interface DiaryHeaderStats {
  visitCount: number;
  uniquePlaceCount: number;
  favoriteCount: number;
}

const MISSING_NAME = "Místo už není v katalogu";

export function isDiarySection(value: string | null): value is DiarySection {
  return value === "visits" || value === "want" || value === "fav" || value === "trips";
}

export function formatVisitDate(visitedAt: string | null): string {
  if (!visitedAt) {
    return "bez data";
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(visitedAt);
  if (!match) {
    return visitedAt;
  }
  return `${Number(match[3])}. ${Number(match[2])}. ${match[1]}`;
}

export function formatStars(rating: number | null): string {
  if (!rating) {
    return "—";
  }
  return "★".repeat(rating) + "☆".repeat(5 - rating);
}

export function shortNote(note: string | null, maxLen = 90): string | null {
  if (!note) {
    return null;
  }
  const compact = note.replace(/\s+/g, " ").trim();
  if (!compact) {
    return null;
  }
  if (compact.length <= maxLen) {
    return compact;
  }
  return `${compact.slice(0, Math.max(1, maxLen - 1)).trimEnd()}…`;
}

export function sortVisitsNewestFirst(visits: StoredVisit[]): StoredVisit[] {
  return [...visits]
    .filter((visit) => !visit.deleted_at)
    .sort(
      (a, b) =>
        (b.visited_at ?? "").localeCompare(a.visited_at ?? "") || b.created_at.localeCompare(a.created_at),
    );
}

export function uniqueVisitedPlaceIds(visits: StoredVisit[]): Set<string> {
  return new Set(sortVisitsNewestFirst(visits).map((visit) => visit.place_id));
}

export function czechCountWord(count: number, one: string, few: string, many: string): string {
  if (count === 1) {
    return one;
  }
  if (count >= 2 && count <= 4) {
    return few;
  }
  return many;
}

export function diaryHeaderStats(visits: StoredVisit[], states: StoredPlaceState[]): DiaryHeaderStats {
  const activeVisits = sortVisitsNewestFirst(visits);
  return {
    visitCount: activeVisits.length,
    uniquePlaceCount: uniqueVisitedPlaceIds(visits).size,
    favoriteCount: states.filter((state) => !state.deleted_at && state.favorite).length,
  };
}

export function formatDiaryStatsLine(stats: DiaryHeaderStats): string {
  const visits = czechCountWord(stats.visitCount, "návštěva", "návštěvy", "návštěv");
  const places = czechCountWord(stats.uniquePlaceCount, "místo", "místa", "míst");
  return `${stats.visitCount} ${visits} · ${stats.uniquePlaceCount} ${places} · ${stats.favoriteCount} oblíbené`;
}

export function resolvePlaceRef(
  placeId: string,
  placesById: Map<string, CatalogPlace>,
  snapshotsById: Map<string, PlaceNameSnapshot>,
): DiaryPlaceRef {
  const place = placesById.get(placeId);
  if (place) {
    return {
      place_id: placeId,
      name: place.name,
      municipality: place.location.municipality,
      missingFromCatalog: false,
    };
  }
  const snapshot = snapshotsById.get(placeId);
  return {
    place_id: placeId,
    name: snapshot?.name?.trim() || MISSING_NAME,
    municipality: snapshot?.municipality ?? null,
    missingFromCatalog: true,
  };
}

export function listVisitRows(
  visits: StoredVisit[],
  placesById: Map<string, CatalogPlace>,
  snapshotsById: Map<string, PlaceNameSnapshot>,
): DiaryVisitRow[] {
  return sortVisitsNewestFirst(visits).map((visit) => {
    const ref = resolvePlaceRef(visit.place_id, placesById, snapshotsById);
    return {
      ...ref,
      visit,
      dateLabel: formatVisitDate(visit.visited_at),
      stars: formatStars(visit.rating),
      notePreview: shortNote(visit.note),
    };
  });
}

function flaggedPlaceRows(
  states: StoredPlaceState[],
  flag: "want_to_visit" | "favorite",
  placesById: Map<string, CatalogPlace>,
  snapshotsById: Map<string, PlaceNameSnapshot>,
): DiaryPlaceRef[] {
  const rows = states
    .filter((state) => !state.deleted_at && state[flag])
    .map((state) => resolvePlaceRef(state.place_id, placesById, snapshotsById));
  return rows.sort((a, b) => a.name.localeCompare(b.name, "cs"));
}

export function listWantToVisitRows(
  states: StoredPlaceState[],
  placesById: Map<string, CatalogPlace>,
  snapshotsById: Map<string, PlaceNameSnapshot>,
): DiaryPlaceRef[] {
  return flaggedPlaceRows(states, "want_to_visit", placesById, snapshotsById);
}

export function listFavoriteRows(
  states: StoredPlaceState[],
  placesById: Map<string, CatalogPlace>,
  snapshotsById: Map<string, PlaceNameSnapshot>,
): DiaryPlaceRef[] {
  return flaggedPlaceRows(states, "favorite", placesById, snapshotsById);
}
