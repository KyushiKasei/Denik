import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { loadVisitsForPlace, updateTrip, updateVisit } from "./store";
import { stampVisitToday, visitOnDate } from "./stamp";
import { tripTodayProgress } from "./tripToday";
import type { StoredTrip, TripStatus } from "./types";

export function statusFromCounts(doneCount: number, total: number): TripStatus {
  if (total > 0 && doneCount >= total) {
    return "done";
  }
  if (doneCount > 0) {
    return "partial";
  }
  return "planned";
}

export function tripStatusLabel(status: TripStatus | undefined): string {
  if (status === "done") {
    return "hotovo";
  }
  if (status === "partial") {
    return "částečně";
  }
  return "plán";
}

export async function linkVisitToTrip(visit: StoredVisit, tripId: string): Promise<StoredVisit> {
  if (visit.trip_id) {
    return visit;
  }
  return updateVisit(visit.id, {
    visited_at: visit.visited_at,
    rating: visit.rating,
    people: visit.people.join(", "),
    note: visit.note,
    trip_id: tripId,
  });
}

export async function completeTrip(
  trip: StoredTrip,
  placesById: Map<string, CatalogPlace>,
  visits: StoredVisit[],
  today: string,
  options?: { stampMissing?: boolean },
): Promise<{ status: TripStatus; stamped: number; linked: number }> {
  const day = trip.planned_on || today;
  const progress = tripTodayProgress(trip, placesById, visits, day, null);
  let stamped = 0;
  let linked = 0;
  for (const stop of progress.stops) {
    const forPlace = visits.filter((visit) => visit.place_id === stop.placeId && !visit.deleted_at);
    // Jen návštěva toho dne — starší otisk nesmí přijít o svůj trip_id.
    let visit = visitOnDate(forPlace, day);
    if (!visit && options?.stampMissing) {
      const result = await stampVisitToday(stop.placeId, trip.id, day);
      visit = result.visit;
      if (result.created) {
        stamped += 1;
      }
    }
    if (visit) {
      await linkVisitToTrip(visit, trip.id);
      linked += 1;
    }
  }
  const latest = await Promise.all(progress.stops.map((stop) => loadVisitsForPlace(stop.placeId)));
  const done = progress.stops.filter((_stop, index) => {
    const rows = latest[index] ?? [];
    return Boolean(visitOnDate(rows, day) || rows.length > 0);
  }).length;
  const status = statusFromCounts(done, progress.stops.length);
  await updateTrip(trip.id, { status });
  return { status, stamped, linked };
}
