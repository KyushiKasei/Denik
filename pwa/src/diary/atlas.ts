import type { CatalogPlace, StoredVisit } from "../catalog/types";
import type { DiaryFilterSets, PlaceFilters } from "../catalog/filterPlaces";
import { filterPlaces } from "../catalog/filterPlaces";
import { hasGps } from "../catalog/labels";
import { formatVisitDate } from "./timeline";

export interface AtlasPlace {
  place: CatalogPlace;
  kind: "visited" | "want" | "other";
}

export interface AtlasTimelineEvent {
  visitId: string;
  placeId: string;
  name: string;
  visitedAt: string | null;
  latitude: number;
  longitude: number;
}

export type AtlasCursor = number | "today";

const UNTIL_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function atlasPlaces(
  places: CatalogPlace[],
  filters: PlaceFilters,
  diary: DiaryFilterSets,
  options?: { includeUnvisited?: boolean },
): AtlasPlace[] {
  const includeUnvisited = options?.includeUnvisited === true || Boolean(filters.region);
  const withGps = places.filter(hasGps);
  const filtered = filterPlaces(withGps, { ...filters, query: filters.query }, diary);
  const rows: AtlasPlace[] = [];
  for (const place of filtered) {
    const visited = diary.visitedIds.has(place.id);
    const want = diary.wantIds.has(place.id);
    if (!includeUnvisited && !visited && !want) {
      continue;
    }
    rows.push({
      place,
      kind: visited ? "visited" : want ? "want" : "other",
    });
  }
  return rows;
}

function visitTimeKey(visit: StoredVisit): [number, string, string] {
  if (visit.visited_at) {
    return [0, visit.visited_at, visit.created_at];
  }
  return [1, "", visit.created_at];
}

export function atlasTimeline(visits: StoredVisit[], places: CatalogPlace[]): AtlasTimelineEvent[] {
  const placesById = new Map(places.map((place) => [place.id, place]));
  return visits
    .filter((visit) => !visit.deleted_at)
    .slice()
    .sort((a, b) => {
      const [aBucket, aDate, aCreated] = visitTimeKey(a);
      const [bBucket, bDate, bCreated] = visitTimeKey(b);
      return aBucket - bBucket || aDate.localeCompare(bDate) || aCreated.localeCompare(bCreated);
    })
    .flatMap((visit) => {
      const place = placesById.get(visit.place_id);
      if (!place || !hasGps(place) || place.location.latitude == null || place.location.longitude == null) {
        return [];
      }
      return [
        {
          visitId: visit.id,
          placeId: place.id,
          name: place.name,
          visitedAt: visit.visited_at,
          latitude: place.location.latitude,
          longitude: place.location.longitude,
        } satisfies AtlasTimelineEvent,
      ];
    });
}

export function parseUntilParam(value: string | null | undefined): string | null {
  const raw = (value ?? "").trim();
  if (!UNTIL_DATE.test(raw)) {
    return null;
  }
  return raw;
}

export function timelineIndexForUntil(timeline: AtlasTimelineEvent[], until: string | null): AtlasCursor {
  if (!until) {
    return "today";
  }
  let last = -1;
  for (let index = 0; index < timeline.length; index++) {
    const at = timeline[index].visitedAt;
    if (at && at <= until) {
      last = index;
    }
  }
  return last;
}

export function atlasPlacesAt(
  rows: AtlasPlace[],
  timeline: AtlasTimelineEvent[],
  cursor: AtlasCursor,
): AtlasPlace[] {
  if (cursor === "today") {
    return rows;
  }
  if (cursor < 0) {
    return [];
  }
  const visibleIds = new Set(timeline.slice(0, cursor + 1).map((event) => event.placeId));
  return rows
    .filter((row) => visibleIds.has(row.place.id))
    .map((row) => ({ ...row, kind: "visited" as const }));
}

export function atlasYears(timeline: AtlasTimelineEvent[]): number[] {
  const years = new Set<number>();
  for (const event of timeline) {
    if (event.visitedAt && /^\d{4}/.test(event.visitedAt)) {
      years.add(Number(event.visitedAt.slice(0, 4)));
    }
  }
  return [...years].sort((a, b) => a - b);
}

export function lastIndexForYear(timeline: AtlasTimelineEvent[], year: number): AtlasCursor {
  return timelineIndexForUntil(timeline, `${year}-12-31`);
}

export function atlasActivePlaceId(timeline: AtlasTimelineEvent[], cursor: AtlasCursor): string | null {
  if (cursor === "today" || cursor < 0 || cursor >= timeline.length) {
    return null;
  }
  return timeline[cursor].placeId;
}

export function atlasTimeCaption(timeline: AtlasTimelineEvent[], cursor: AtlasCursor): string {
  if (cursor === "today") {
    return "Dnes";
  }
  if (cursor < 0 || !timeline[cursor]) {
    return "Začátek";
  }
  const event = timeline[cursor];
  return `${formatVisitDate(event.visitedAt)} · ${event.name}`;
}
