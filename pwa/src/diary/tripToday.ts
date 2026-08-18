import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { hasGps } from "../catalog/labels";
import { dateAtNoon, dayOpenState, hoursLineForPlace } from "../catalog/openingHours";
import { haversineKm } from "../geo/haversine";
import { orderedStops } from "./tripPlan";
import type { StoredTrip } from "./types";
import { uniqueVisitedPlaceIds } from "./timeline";

export interface TripTodayStop {
  placeId: string;
  place: CatalogPlace | undefined;
  name: string;
  done: boolean;
  stampedToday: boolean;
  kmFromHere: number | null;
  openState: "open" | "closed" | "unknown";
  hoursLine: string | null;
  official: string | null;
  tickets: string | null;
}

export interface TripTodayProgress {
  trip: StoredTrip;
  stops: TripTodayStop[];
  next: TripTodayStop | null;
  doneCount: number;
  allDone: boolean;
  airKm: number | null;
}

export function tripTodayProgress(
  trip: StoredTrip,
  placesById: Map<string, CatalogPlace>,
  visits: StoredVisit[],
  today: string,
  here: { latitude: number; longitude: number } | null,
): TripTodayProgress {
  const visited = uniqueVisitedPlaceIds(visits);
  const todayIds = new Set(
    visits.filter((visit) => !visit.deleted_at && visit.visited_at === today).map((visit) => visit.place_id),
  );
  const stops: TripTodayStop[] = orderedStops(trip).map((stop) => {
    const place = placesById.get(stop.place_id);
    const kmFromHere =
      here && place && hasGps(place)
        ? haversineKm(here.latitude, here.longitude, place.location.latitude, place.location.longitude)
        : null;
    const when = dateAtNoon(today);
    return {
      placeId: stop.place_id,
      place,
      name: place?.name ?? "Místo",
      done: visited.has(stop.place_id),
      stampedToday: todayIds.has(stop.place_id),
      kmFromHere,
      openState: place ? dayOpenState(place, when) : "unknown",
      hoursLine: place ? hoursLineForPlace(place, when) : null,
      official: place?.links.official ?? null,
      tickets: place?.links.tickets ?? null,
    };
  });
  const next = stops.find((stop) => !stop.done) ?? null;
  const knownKm = stops
    .map((stop, index) => {
      if (index === 0) {
        return null;
      }
      const from = stops[index - 1]?.place;
      const to = stop.place;
      if (!from || !to || !hasGps(from) || !hasGps(to)) {
        return null;
      }
      return haversineKm(from.location.latitude, from.location.longitude, to.location.latitude, to.location.longitude);
    })
    .filter((km): km is number => km != null);
  return {
    trip,
    stops,
    next,
    doneCount: stops.filter((stop) => stop.done).length,
    allDone: stops.length > 0 && stops.every((stop) => stop.done),
    airKm: knownKm.length ? knownKm.reduce((sum, km) => sum + km, 0) : null,
  };
}
