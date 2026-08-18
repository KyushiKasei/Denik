import type { CatalogPlace, StoredVisit, VisitabilityCode } from "../catalog/types";
import { hasGps } from "../catalog/labels";
import { isGone, isWeakStub, isWorthVisiting, visitScore } from "../catalog/visitWorth";
import { DEFAULT_RADIUS_KM, haversineKm } from "../geo/haversine";
import type { NearbyHit } from "../geo/nearby";
import { matchCzechRegion } from "./regions";
import { sortVisitsNewestFirst, uniqueVisitedPlaceIds } from "./timeline";
import { placeMatchesMood, type TodayMood } from "../catalog/moods";

const OPENISH: ReadonlySet<VisitabilityCode> = new Set(["REGULAR", "FREE_ACCESS", "EXTERIOR_ONLY"]);
const CLOSED: ReadonlySet<VisitabilityCode> = new Set(["CLOSED", "EXTINCT", "PRIVATE", "TEMPORARILY_CLOSED"]);

export interface DiscoverContext {
  tripPlaceIds?: ReadonlySet<string>;
  visitedRegionIds?: ReadonlySet<string>;
  month?: number;
}

export function discoverScore(place: CatalogPlace, ctx: DiscoverContext = {}): number {
  if (isGone(place)) {
    return -1000;
  }
  let score = visitScore(place);
  if (ctx.tripPlaceIds?.has(place.id)) {
    score += 50;
  }
  const region = matchCzechRegion(place.location.region);
  if (region && ctx.visitedRegionIds && !ctx.visitedRegionIds.has(region.id)) {
    score += 40;
  }
  if (OPENISH.has(place.visitability)) {
    score += 20;
  }
  const month = ctx.month ?? new Date().getMonth() + 1;
  if (place.visitability === "SEASONAL" && month >= 4 && month <= 10) {
    score += 15;
  }
  if (CLOSED.has(place.visitability)) {
    score -= 30;
  }
  if (place.unesco) {
    score += 8;
  }
  if (isWeakStub(place)) {
    score -= 40;
  }
  return score;
}

function hashString(value: string): number {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function lastActiveVisit(visits: StoredVisit[]): StoredVisit | null {
  return sortVisitsNewestFirst(visits)[0] ?? null;
}

export function nearbyUnvisited(
  places: CatalogPlace[],
  origin: { latitude: number; longitude: number } | null,
  radiusKm: number,
  visits: StoredVisit[],
  limit = 3,
  mood: TodayMood = "",
): NearbyHit[] {
  if (!origin) {
    return [];
  }
  const visitedIds = uniqueVisitedPlaceIds(visits);
  const radius = radiusKm || DEFAULT_RADIUS_KM;
  const hits: NearbyHit[] = [];
  for (const place of places) {
    if (visitedIds.has(place.id) || !hasGps(place) || !isWorthVisiting(place) || !placeMatchesMood(place, mood)) {
      continue;
    }
    const km = haversineKm(origin.latitude, origin.longitude, place.location.latitude, place.location.longitude);
    if (km == null || km > radius) {
      continue;
    }
    hits.push({ place, km });
  }
  hits.sort((a, b) => a.km - b.km || a.place.name.localeCompare(b.place.name, "cs"));
  return hits.slice(0, limit);
}

export function discoverPool(
  places: CatalogPlace[],
  visits: StoredVisit[],
  origin: { latitude: number; longitude: number } | null,
  radiusKm: number,
  mood: TodayMood = "",
): CatalogPlace[] {
  const visitedIds = uniqueVisitedPlaceIds(visits);
  const unvisited = places.filter(
    (place) => !visitedIds.has(place.id) && hasGps(place) && !isGone(place) && placeMatchesMood(place, mood),
  );
  if (!origin) {
    return unvisited;
  }
  const nearby = unvisited.filter((place) => {
    const km = haversineKm(origin.latitude, origin.longitude, place.location.latitude, place.location.longitude);
    return km != null && km <= radiusKm;
  });
  return nearby.length > 0 ? nearby : unvisited;
}

export function pickDiscoverToday(
  places: CatalogPlace[],
  visits: StoredVisit[],
  origin: { latitude: number; longitude: number } | null,
  radiusKm: number,
  dayIso: string,
  skipIds: ReadonlySet<string> = new Set(),
  ctx: DiscoverContext = {},
  mood: TodayMood = "",
): CatalogPlace | null {
  const pool = discoverPool(places, visits, origin, radiusKm, mood).filter((place) => !skipIds.has(place.id));
  const fallback = pool.length > 0 ? pool : discoverPool(places, visits, origin, radiusKm, mood);
  if (fallback.length === 0) {
    return null;
  }
  const scored = fallback.map((place) => ({ place, score: discoverScore(place, ctx) }));
  const best = Math.max(...scored.map((row) => row.score));
  const top = scored.filter((row) => row.score === best).map((row) => row.place);
  const index = hashString(`${dayIso}:${top.map((place) => place.id).join(",")}`) % top.length;
  return top[index] ?? null;
}
