import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { uniqueVisitedPlaceIds } from "./timeline";
import type { StoredTrip } from "./types";

export interface YearbookStats {
  year: number;
  visitCount: number;
  uniquePlaces: number;
  favoriteVisits: number;
  tripCount: number;
  topRated: Array<{ placeId: string; name: string; rating: number }>;
  people: string[];
}

export function visitYear(visitedAt: string | null, fallbackYear: number): number | null {
  if (!visitedAt) {
    return fallbackYear;
  }
  const match = /^(\d{4})/.exec(visitedAt);
  return match ? Number(match[1]) : null;
}

export function yearbookFor(
  year: number,
  visits: StoredVisit[],
  places: CatalogPlace[],
  trips: StoredTrip[],
  favoriteIds: Set<string> = new Set(),
): YearbookStats {
  const placesById = new Map(places.map((place) => [place.id, place]));
  const live = visits.filter((visit) => !visit.deleted_at && visitYear(visit.visited_at, year) === year);
  const people = new Set<string>();
  for (const visit of live) {
    for (const name of visit.people) {
      people.add(name);
    }
  }
  const rated = live
    .filter((visit) => visit.rating != null)
    .sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0) || (a.visited_at ?? "").localeCompare(b.visited_at ?? ""))
    .slice(0, 3)
    .map((visit) => ({
      placeId: visit.place_id,
      name: placesById.get(visit.place_id)?.name ?? "Místo",
      rating: visit.rating ?? 0,
    }));
  const yearTrips = trips.filter((trip) => !trip.deleted_at && (trip.planned_on ?? "").startsWith(String(year)));
  return {
    year,
    visitCount: live.length,
    uniquePlaces: uniqueVisitedPlaceIds(live).size,
    favoriteVisits: live.filter((visit) => favoriteIds.has(visit.place_id)).length,
    tripCount: yearTrips.length,
    topRated: rated,
    people: [...people].sort((a, b) => a.localeCompare(b, "cs")),
  };
}

export function currentYear(now = new Date()): number {
  return now.getFullYear();
}
