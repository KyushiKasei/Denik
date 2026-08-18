import type { StoredVisit } from "../catalog/types";
import { addVisit, loadVisitsForPlace, savePlaceState, updateVisit } from "./store";
import { todayIsoDate } from "./ids";

const inflight = new Map<string, Promise<{ visit: StoredVisit; created: boolean }>>();

export function visitOnDate(visits: StoredVisit[], day: string): StoredVisit | undefined {
  const needle = day.trim();
  return visits.find((visit) => !visit.deleted_at && (visit.visited_at || "").trim() === needle);
}

async function attachTripIfMissing(visit: StoredVisit, tripId?: string | null): Promise<StoredVisit> {
  if (!tripId || visit.trip_id) {
    return visit;
  }
  const live = visitOnDate(await loadVisitsForPlace(visit.place_id), visit.visited_at || "") ?? visit;
  if (live.trip_id) {
    return live;
  }
  return updateVisit(live.id, {
    visited_at: live.visited_at,
    rating: live.rating,
    people: live.people.join(", "),
    note: live.note,
    trip_id: tripId,
  });
}

export async function stampVisitToday(
  placeId: string,
  tripId?: string | null,
  visitedAt?: string,
): Promise<{ visit: StoredVisit; created: boolean }> {
  const today = (visitedAt || "").trim() || todayIsoDate();
  // Zámek jen místo+den — tripId by jinak pustil dvě souběžná razítka (mapa vs výlet).
  const key = `${placeId}|${today}`;
  const pending = inflight.get(key);
  if (pending) {
    const first = await pending;
    return { visit: await attachTripIfMissing(first.visit, tripId), created: false };
  }
  const run = (async () => {
    const existing = visitOnDate(await loadVisitsForPlace(placeId), today);
    if (existing) {
      return { visit: await attachTripIfMissing(existing, tripId), created: false };
    }
    const visit = await addVisit({
      place_id: placeId,
      visited_at: today,
      rating: null,
      people: "",
      note: null,
      trip_id: tripId ?? null,
    });
    await savePlaceState(placeId, { want_to_visit: false });
    return { visit, created: true };
  })().finally(() => {
    inflight.delete(key);
  });
  inflight.set(key, run);
  return run;
}
