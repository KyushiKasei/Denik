import type { StoredPlaceState, StoredVisit } from "../catalog/types";
import { getPlaceSnapshot, loadPlaces } from "../catalog/importCatalog";
import { loadPlaceState, loadPlaceStates, loadVisits, loadVisitsForPlace } from "./store";

export interface OrphanGroup {
  place_id: string;
  visits: StoredVisit[];
  state: StoredPlaceState | null;
  last_name?: string | null;
  last_municipality?: string | null;
}

export function catalogPlaceIds(places: { id: string }[]): Set<string> {
  return new Set(places.map((place) => place.id));
}

export function groupOrphans(
  visits: StoredVisit[],
  states: StoredPlaceState[],
  placeIds: Set<string>,
): OrphanGroup[] {
  const byPlace = new Map<string, OrphanGroup>();

  const ensure = (placeId: string): OrphanGroup => {
    const existing = byPlace.get(placeId);
    if (existing) {
      return existing;
    }
    const created: OrphanGroup = { place_id: placeId, visits: [], state: null };
    byPlace.set(placeId, created);
    return created;
  };

  for (const visit of visits) {
    if (visit.deleted_at || placeIds.has(visit.place_id)) {
      continue;
    }
    ensure(visit.place_id).visits.push(visit);
  }
  for (const state of states) {
    if (state.deleted_at || placeIds.has(state.place_id)) {
      continue;
    }
    const hasContent = state.want_to_visit || state.favorite || Boolean(state.personal_note);
    if (!hasContent && !byPlace.has(state.place_id)) {
      continue;
    }
    ensure(state.place_id).state = state;
  }

  return [...byPlace.values()].sort((a, b) => a.place_id.localeCompare(b.place_id));
}

export function countVisitsForRemovedPlaces(visits: StoredVisit[], removedIds: string[]): number {
  const removed = new Set(removedIds);
  return visits.filter((visit) => !visit.deleted_at && removed.has(visit.place_id)).length;
}

export async function listOrphanedDiary(): Promise<OrphanGroup[]> {
  const [places, visits, states] = await Promise.all([loadPlaces(), loadVisits(), loadPlaceStates()]);
  const groups = groupOrphans(visits, states, catalogPlaceIds(places));
  return Promise.all(
    groups.map(async (group) => {
      const snapshot = await getPlaceSnapshot(group.place_id);
      return {
        ...group,
        last_name: snapshot?.name ?? null,
        last_municipality: snapshot?.municipality ?? null,
      };
    }),
  );
}

export async function isOrphanPlace(placeId: string): Promise<boolean> {
  const places = await loadPlaces();
  if (places.some((place) => place.id === placeId)) {
    return false;
  }
  const [visits, state] = await Promise.all([loadVisitsForPlace(placeId), loadPlaceState(placeId)]);
  return visits.length > 0 || state != null;
}
