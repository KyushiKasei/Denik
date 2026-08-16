import type { CatalogPlace } from "../catalog/types";
import { haversineKm } from "../geo/haversine";
import type { StoredTrip, StoredTripStop } from "./types";

export function orderedStops(trip: StoredTrip): StoredTripStop[] {
  return [...trip.stops].sort((a, b) => a.sort_order - b.sort_order);
}

export function consecutiveStopKm(
  stops: StoredTripStop[],
  placesById: Map<string, CatalogPlace>,
): Array<number | null> {
  const gaps: Array<number | null> = [];
  for (let i = 0; i < stops.length - 1; i += 1) {
    const from = placesById.get(stops[i].place_id)?.location;
    const to = placesById.get(stops[i + 1].place_id)?.location;
    gaps.push(
      haversineKm(from?.latitude, from?.longitude, to?.latitude, to?.longitude),
    );
  }
  return gaps;
}

export function tripAirKm(trip: StoredTrip, placesById: Map<string, CatalogPlace>): number | null {
  const gaps = consecutiveStopKm(orderedStops(trip), placesById);
  const known = gaps.filter((km): km is number => km != null);
  if (known.length === 0) {
    return null;
  }
  return known.reduce((sum, km) => sum + km, 0);
}
