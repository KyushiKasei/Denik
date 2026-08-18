import type { CatalogPlace } from "../catalog/types";
import { hasGps } from "../catalog/labels";
import { dateAtNoon, isClosedOnDate } from "../catalog/openingHours";
import { haversineKm } from "../geo/haversine";

export const WEEKEND_MIN_STOPS = 2;
export const WEEKEND_MAX_STOPS = 4;
export const WEEKEND_DEFAULT_STOPS = 3;
export const WEEKEND_DEFAULT_RADIUS_KM = 50;

export interface WeekendPlanInput {
  places: CatalogPlace[];
  wantIds: ReadonlySet<string>;
  origin: { latitude: number; longitude: number } | null;
  region?: string;
  radiusKm: number;
  stopCount: number;
  plannedOn?: string | null;
}

export function weekendClosedOnDate(place: CatalogPlace, plannedOn?: string | null): boolean {
  if (!plannedOn) {
    return isClosedOnDate(place, new Date());
  }
  return isClosedOnDate(place, dateAtNoon(plannedOn));
}

function withCoords(
  place: CatalogPlace,
): place is CatalogPlace & { location: CatalogPlace["location"] & { latitude: number; longitude: number } } {
  return hasGps(place) && place.location.latitude != null && place.location.longitude != null;
}

export function clampWeekendStops(raw: number | string | null | undefined): number {
  const value = Math.round(Number(raw));
  if (!Number.isFinite(value)) {
    return WEEKEND_DEFAULT_STOPS;
  }
  return Math.max(WEEKEND_MIN_STOPS, Math.min(WEEKEND_MAX_STOPS, value));
}

/** Greedy nearest-neighbor. Bez silničního routingu — vzdušná čára. */
export function greedyOrder(
  places: CatalogPlace[],
  start: { latitude: number; longitude: number } | null,
): CatalogPlace[] {
  const remaining = places.filter(withCoords);
  if (remaining.length === 0) {
    return [];
  }
  const ordered: CatalogPlace[] = [];
  let cursor = start;
  if (!cursor) {
    remaining.sort((a, b) => a.name.localeCompare(b.name, "cs"));
    const first = remaining.shift();
    if (!first || !withCoords(first)) {
      return [];
    }
    ordered.push(first);
    cursor = { latitude: first.location.latitude, longitude: first.location.longitude };
  }
  while (remaining.length > 0 && cursor) {
    let bestIndex = 0;
    let bestKm = Number.POSITIVE_INFINITY;
    for (let i = 0; i < remaining.length; i += 1) {
      const place = remaining[i];
      if (!place || !withCoords(place)) {
        continue;
      }
      const km = haversineKm(cursor.latitude, cursor.longitude, place.location.latitude, place.location.longitude);
      if (km != null && km < bestKm) {
        bestKm = km;
        bestIndex = i;
      }
    }
    const next = remaining.splice(bestIndex, 1)[0];
    if (!next || !withCoords(next)) {
      break;
    }
    ordered.push(next);
    cursor = { latitude: next.location.latitude, longitude: next.location.longitude };
  }
  return ordered;
}

export function weekendCandidates(
  input: WeekendPlanInput,
  options?: { ignoreHours?: boolean },
): CatalogPlace[] {
  const radius = input.radiusKm > 0 ? input.radiusKm : WEEKEND_DEFAULT_RADIUS_KM;
  const out: CatalogPlace[] = [];
  for (const place of input.places) {
    if (!input.wantIds.has(place.id) || !withCoords(place)) {
      continue;
    }
    if (input.region && place.location.region !== input.region) {
      continue;
    }
    if (input.origin) {
      const km = haversineKm(
        input.origin.latitude,
        input.origin.longitude,
        place.location.latitude,
        place.location.longitude,
      );
      if (km == null || km > radius) {
        continue;
      }
    }
    if (!options?.ignoreHours && weekendClosedOnDate(place, input.plannedOn)) {
      continue;
    }
    out.push(place);
  }
  return out;
}

export function weekendClosedSkipped(input: WeekendPlanInput): CatalogPlace[] {
  const all = weekendCandidates(input, { ignoreHours: true });
  const openIds = new Set(weekendCandidates(input).map((place) => place.id));
  return all.filter((place) => !openIds.has(place.id));
}

export function suggestWeekendPlaces(input: WeekendPlanInput): CatalogPlace[] {
  const stopCount = clampWeekendStops(input.stopCount);
  const candidates = weekendCandidates(input);
  const ordered = greedyOrder(candidates, input.origin);
  return ordered.slice(0, stopCount);
}

export function reorderPlaceIds(
  placeIds: string[],
  placesById: Map<string, CatalogPlace>,
  start: { latitude: number; longitude: number } | null,
): string[] {
  const places = placeIds
    .map((id) => placesById.get(id))
    .filter((place): place is CatalogPlace => Boolean(place));
  const ordered = greedyOrder(places, start);
  const seen = new Set(ordered.map((place) => place.id));
  const missing = placeIds.filter((id) => !seen.has(id));
  return [...ordered.map((place) => place.id), ...missing];
}
