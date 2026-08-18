import type { CatalogPlace } from "../catalog/types";
import type { DiaryFilterSets, PlaceFilters } from "../catalog/filterPlaces";
import { filterPlaces } from "../catalog/filterPlaces";
import { hasGps } from "../catalog/labels";
import { haversineKm } from "./haversine";
import { capNearbyHits, type NearbyHit, type NearbyList } from "./nearby";

export const DEFAULT_CORRIDOR_KM = 15;
export const MIN_CORRIDOR_KM = 5;
export const MAX_CORRIDOR_KM = 40;
export const CORRIDOR_STEP_KM = 5;

export interface LatLon {
  latitude: number;
  longitude: number;
}

export function clampCorridorKm(raw: number | string | null | undefined): number {
  if (raw == null || raw === "") {
    return DEFAULT_CORRIDOR_KM;
  }
  const value = Math.round(Number(String(raw).replace(",", ".")));
  if (!Number.isFinite(value)) {
    return DEFAULT_CORRIDOR_KM;
  }
  return Math.max(MIN_CORRIDOR_KM, Math.min(MAX_CORRIDOR_KM, value));
}

function valid(point: LatLon | null | undefined): point is LatLon {
  return (
    point != null &&
    Number.isFinite(point.latitude) &&
    Number.isFinite(point.longitude) &&
    point.latitude >= -90 &&
    point.latitude <= 90 &&
    point.longitude >= -180 &&
    point.longitude <= 180
  );
}

/** Nejbližší bod na úsečce AB (interpolace lat/lon stačí pro ČR). */
export function closestPointOnSegment(point: LatLon, a: LatLon, b: LatLon): LatLon {
  const dx = b.longitude - a.longitude;
  const dy = b.latitude - a.latitude;
  const len2 = dx * dx + dy * dy;
  if (len2 < 1e-18) {
    return a;
  }
  const t = Math.max(
    0,
    Math.min(1, ((point.longitude - a.longitude) * dx + (point.latitude - a.latitude) * dy) / len2),
  );
  return { latitude: a.latitude + t * dy, longitude: a.longitude + t * dx };
}

export function distanceToSegmentKm(point: LatLon, a: LatLon, b: LatLon): number | null {
  if (!valid(point) || !valid(a) || !valid(b)) {
    return null;
  }
  const closest = closestPointOnSegment(point, a, b);
  return haversineKm(point.latitude, point.longitude, closest.latitude, closest.longitude);
}

export function alongSegmentKm(point: LatLon, a: LatLon, b: LatLon): number | null {
  if (!valid(point) || !valid(a) || !valid(b)) {
    return null;
  }
  const closest = closestPointOnSegment(point, a, b);
  return haversineKm(a.latitude, a.longitude, closest.latitude, closest.longitude);
}

/** Všechna GPS místa v bufferu úsečky — bez katalogových filtrů (pro počty ve filtrech). */
export function corridorHits(
  places: CatalogPlace[],
  start: LatLon,
  end: LatLon,
  corridorKm: number,
): NearbyHit[] {
  const buffer = clampCorridorKm(corridorKm);
  const hits: NearbyHit[] = [];
  for (const place of places) {
    if (!hasGps(place)) {
      continue;
    }
    const lat = place.location.latitude;
    const lon = place.location.longitude;
    if (lat == null || lon == null) {
      continue;
    }
    const point = { latitude: lat, longitude: lon };
    const km = distanceToSegmentKm(point, start, end);
    if (km == null || km > buffer) {
      continue;
    }
    hits.push({ place, km });
  }
  return hits;
}

export function placesInCorridor(
  places: CatalogPlace[],
  start: LatLon,
  end: LatLon,
  corridorKm: number,
): CatalogPlace[] {
  return corridorHits(places, start, end, corridorKm).map((hit) => hit.place);
}

export function placesAlongCorridor(
  places: CatalogPlace[],
  start: LatLon,
  end: LatLon,
  corridorKm: number,
  filters: PlaceFilters,
  diary?: DiaryFilterSets,
): NearbyList {
  const skippedNoGps = places.filter((place) => !hasGps(place)).length;
  const geo = corridorHits(places, start, end, corridorKm);
  const allowed = new Set(
    filterPlaces(
      geo.map((hit) => hit.place),
      { ...filters, query: "" },
      diary,
    ).map((place) => place.id),
  );
  const hits = geo.filter((hit) => allowed.has(hit.place.id));
  hits.sort((a, b) => {
    const aAlong =
      alongSegmentKm(
        { latitude: a.place.location.latitude as number, longitude: a.place.location.longitude as number },
        start,
        end,
      ) ?? 0;
    const bAlong =
      alongSegmentKm(
        { latitude: b.place.location.latitude as number, longitude: b.place.location.longitude as number },
        start,
        end,
      ) ?? 0;
    return aAlong - bAlong || a.km - b.km || a.place.name.localeCompare(b.place.name, "cs");
  });
  return { skippedNoGps, ...capNearbyHits(hits) };
}
