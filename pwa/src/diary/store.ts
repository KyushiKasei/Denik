import type { StoredPlaceState, StoredVisit } from "../catalog/types";
import { persistStorage } from "../storage/persist";
import { db } from "../db";
import { newVisitId, nowIso, todayIsoDate } from "./ids";
import { mergePlaceStates, mergeTrips, mergeVisits } from "./merge";
import { DIARY_SCHEMA_VERSION, type Diary, type DiaryMergeCounts, type DiaryMeta, type StoredTrip, type TripOrigin } from "./types";
import { validateDiary } from "./validate";

const MAX_BACKUPS = 5;
const ACTIVE_TRIP_KEY = "pamatky.activeTripId";

async function metaValue<T>(key: string): Promise<T | undefined> {
  const row = await db.meta.get(key);
  return row?.value as T | undefined;
}

async function setMeta(key: string, value: unknown): Promise<void> {
  await db.meta.put({ key, value });
}

export async function loadVisits(includeDeleted = false): Promise<StoredVisit[]> {
  const rows = await db.visits.toArray();
  return includeDeleted ? rows : rows.filter((row) => !row.deleted_at);
}

export async function loadVisitsForPlace(placeId: string): Promise<StoredVisit[]> {
  const rows = await db.visits.where("place_id").equals(placeId).toArray();
  return rows
    .filter((row) => !row.deleted_at)
    .sort((a, b) => (b.visited_at ?? "").localeCompare(a.visited_at ?? "") || b.created_at.localeCompare(a.created_at));
}

export async function loadPlaceState(placeId: string): Promise<StoredPlaceState | undefined> {
  const row = await db.place_states.get(placeId);
  if (!row || row.deleted_at) {
    return undefined;
  }
  return row;
}

export async function loadPlaceStates(includeDeleted = false): Promise<StoredPlaceState[]> {
  const rows = await db.place_states.toArray();
  return includeDeleted ? rows : rows.filter((row) => !row.deleted_at);
}

export async function visitedPlaceIds(): Promise<Set<string>> {
  const visits = await loadVisits();
  return new Set(visits.map((visit) => visit.place_id));
}

export async function wantToVisitPlaceIds(): Promise<Set<string>> {
  const states = await loadPlaceStates();
  return new Set(states.filter((state) => state.want_to_visit).map((state) => state.place_id));
}

export async function favoritePlaceIds(): Promise<Set<string>> {
  const states = await loadPlaceStates();
  return new Set(states.filter((state) => state.favorite).map((state) => state.place_id));
}

function parsePeople(raw: string): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const part of raw.split(/[,;\n]/)) {
    const name = part.trim();
    if (!name || seen.has(name)) {
      continue;
    }
    seen.add(name);
    names.push(name);
  }
  return names;
}

export async function addVisit(input: {
  place_id: string;
  visited_at: string | null;
  rating: number | null;
  people: string;
  note: string | null;
}): Promise<StoredVisit> {
  const now = nowIso();
  const visit: StoredVisit = {
    id: newVisitId(),
    place_id: input.place_id,
    visited_at: input.visited_at || todayIsoDate(),
    rating: input.rating,
    people: parsePeople(input.people),
    note: input.note?.trim() ? input.note.trim() : null,
    created_at: now,
    updated_at: now,
    deleted_at: null,
  };
  await db.visits.put(visit);
  await persistStorage();
  return visit;
}

export async function updateVisit(
  id: string,
  input: {
    visited_at: string | null;
    rating: number | null;
    people: string;
    note: string | null;
  },
): Promise<StoredVisit> {
  const visit = await db.visits.get(id);
  if (!visit || visit.deleted_at) {
    throw new Error("Návštěva už neexistuje.");
  }
  const next: StoredVisit = {
    ...visit,
    visited_at: input.visited_at || todayIsoDate(),
    rating: input.rating,
    people: parsePeople(input.people),
    note: input.note?.trim() ? input.note.trim() : null,
    updated_at: nowIso(),
  };
  await db.visits.put(next);
  await persistStorage();
  return next;
}

export async function softDeleteVisit(id: string): Promise<void> {
  const visit = await db.visits.get(id);
  if (!visit || visit.deleted_at) {
    return;
  }
  await db.visits.put({ ...visit, deleted_at: nowIso(), updated_at: nowIso() });
  await persistStorage();
}

export async function savePlaceState(
  placeId: string,
  patch: Partial<Pick<StoredPlaceState, "want_to_visit" | "favorite" | "personal_note">>,
): Promise<StoredPlaceState> {
  const current = await db.place_states.get(placeId);
  const now = nowIso();
  const next: StoredPlaceState = {
    place_id: placeId,
    want_to_visit: patch.want_to_visit ?? current?.want_to_visit ?? false,
    favorite: patch.favorite ?? current?.favorite ?? false,
    personal_note: patch.personal_note !== undefined ? patch.personal_note : (current?.personal_note ?? null),
    updated_at: now,
    deleted_at: null,
  };
  await db.place_states.put(next);
  await persistStorage();
  return next;
}

export async function loadTrips(includeDeleted = false): Promise<StoredTrip[]> {
  const rows = await db.trips.toArray();
  const live = includeDeleted ? rows : rows.filter((row) => !row.deleted_at);
  return live.sort(
    (a, b) =>
      (b.planned_on ?? "").localeCompare(a.planned_on ?? "") || b.updated_at.localeCompare(a.updated_at),
  );
}

export async function getTrip(id: string): Promise<StoredTrip | undefined> {
  const row = await db.trips.get(id);
  if (!row || row.deleted_at) {
    return undefined;
  }
  return row;
}

export function loadActiveTripId(): string | null {
  if (typeof localStorage === "undefined") {
    return null;
  }
  return localStorage.getItem(ACTIVE_TRIP_KEY);
}

export function saveActiveTripId(id: string | null): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  if (!id) {
    localStorage.removeItem(ACTIVE_TRIP_KEY);
    return;
  }
  localStorage.setItem(ACTIVE_TRIP_KEY, id);
}

export async function createTrip(input: {
  name: string;
  planned_on?: string | null;
  origin?: TripOrigin | null;
  notes?: string | null;
}): Promise<StoredTrip> {
  const now = nowIso();
  const trip: StoredTrip = {
    id: newVisitId(),
    name: input.name.trim() || "Výlet",
    planned_on: input.planned_on || todayIsoDate(),
    origin: input.origin ?? null,
    notes: input.notes?.trim() ? input.notes.trim() : null,
    stops: [],
    created_at: now,
    updated_at: now,
    deleted_at: null,
  };
  await db.trips.put(trip);
  saveActiveTripId(trip.id);
  await persistStorage();
  return trip;
}

export async function updateTrip(
  id: string,
  patch: Partial<Pick<StoredTrip, "name" | "planned_on" | "origin" | "notes" | "stops">>,
): Promise<StoredTrip> {
  const trip = await db.trips.get(id);
  if (!trip || trip.deleted_at) {
    throw new Error("Výlet už neexistuje.");
  }
  const next: StoredTrip = {
    ...trip,
    ...patch,
    name: patch.name != null ? patch.name.trim() || trip.name : trip.name,
    notes: patch.notes !== undefined ? (patch.notes?.trim() ? patch.notes.trim() : null) : trip.notes,
    updated_at: nowIso(),
  };
  await db.trips.put(next);
  await persistStorage();
  return next;
}

export async function softDeleteTrip(id: string): Promise<void> {
  const trip = await db.trips.get(id);
  if (!trip || trip.deleted_at) {
    return;
  }
  await db.trips.put({ ...trip, deleted_at: nowIso(), updated_at: nowIso() });
  if (loadActiveTripId() === id) {
    saveActiveTripId(null);
  }
  await persistStorage();
}

export async function addPlaceToTrip(tripId: string, placeId: string): Promise<StoredTrip> {
  const trip = await getTrip(tripId);
  if (!trip) {
    throw new Error("Výlet už neexistuje.");
  }
  if (trip.stops.some((stop) => stop.place_id === placeId)) {
    return trip;
  }
  const sort_order = trip.stops.reduce((max, stop) => Math.max(max, stop.sort_order), -1) + 1;
  return updateTrip(tripId, {
    stops: [...trip.stops, { place_id: placeId, sort_order, note: null }],
  });
}

export async function addPlaceToActiveTrip(
  placeId: string,
  origin?: TripOrigin | null,
): Promise<StoredTrip> {
  const activeId = loadActiveTripId();
  if (activeId) {
    const existing = await getTrip(activeId);
    if (existing) {
      return addPlaceToTrip(existing.id, placeId);
    }
  }
  const created = await createTrip({
    name: "Výlet",
    planned_on: todayIsoDate(),
    origin: origin ?? null,
  });
  return addPlaceToTrip(created.id, placeId);
}

export async function removeStopFromTrip(tripId: string, placeId: string): Promise<StoredTrip> {
  const trip = await getTrip(tripId);
  if (!trip) {
    throw new Error("Výlet už neexistuje.");
  }
  const stops = trip.stops
    .filter((stop) => stop.place_id !== placeId)
    .map((stop, index) => ({ ...stop, sort_order: index }));
  return updateTrip(tripId, { stops });
}

export async function moveTripStop(tripId: string, placeId: string, direction: -1 | 1): Promise<StoredTrip> {
  const trip = await getTrip(tripId);
  if (!trip) {
    throw new Error("Výlet už neexistuje.");
  }
  const stops = [...trip.stops].sort((a, b) => a.sort_order - b.sort_order);
  const index = stops.findIndex((stop) => stop.place_id === placeId);
  const nextIndex = index + direction;
  if (index < 0 || nextIndex < 0 || nextIndex >= stops.length) {
    return trip;
  }
  const swap = stops[index];
  stops[index] = stops[nextIndex];
  stops[nextIndex] = swap;
  return updateTrip(tripId, {
    stops: stops.map((stop, order) => ({ ...stop, sort_order: order })),
  });
}

export async function buildDiary(): Promise<Diary> {
  const [visits, place_states, trips] = await Promise.all([
    loadVisits(true),
    loadPlaceStates(true),
    loadTrips(true),
  ]);
  const diary: Diary = {
    schema_version: DIARY_SCHEMA_VERSION,
    exported_at: nowIso(),
    exported_from: "pwa",
    place_states,
    visits,
    trips,
  };
  return validateDiary(diary);
}

async function snapshotDiary(): Promise<void> {
  const diary = await buildDiary();
  await db.diary_backups.add({ created_at: nowIso(), diary });
  const all = await db.diary_backups.orderBy("created_at").toArray();
  const extra = all.slice(0, Math.max(0, all.length - MAX_BACKUPS));
  await Promise.all(extra.map((row) => (row.id != null ? db.diary_backups.delete(row.id) : Promise.resolve())));
}

export async function importDiary(diary: Diary): Promise<DiaryMergeCounts> {
  validateDiary(diary);
  await snapshotDiary();
  const [localVisits, localStates, localTrips] = await Promise.all([
    loadVisits(true),
    loadPlaceStates(true),
    loadTrips(true),
  ]);
  const visits = mergeVisits(localVisits, diary.visits);
  const states = mergePlaceStates(localStates, diary.place_states);
  const trips = mergeTrips(localTrips, diary.trips ?? []);

  await db.transaction("rw", db.visits, db.place_states, db.trips, db.meta, async () => {
    await db.visits.clear();
    await db.place_states.clear();
    await db.trips.clear();
    if (visits.next.length > 0) {
      await db.visits.bulkPut(visits.next);
    }
    if (states.next.length > 0) {
      await db.place_states.bulkPut(states.next);
    }
    if (trips.next.length > 0) {
      await db.trips.bulkPut(trips.next);
    }
    await setMeta("last_diary_import_at", nowIso());
  });
  await persistStorage();

  return {
    visitsInserted: visits.counts.visitsInserted,
    visitsUpdated: visits.counts.visitsUpdated,
    visitsUnchanged: visits.counts.visitsUnchanged,
    statesInserted: states.counts.statesInserted,
    statesUpdated: states.counts.statesUpdated,
    statesUnchanged: states.counts.statesUnchanged,
    tripsInserted: trips.counts.tripsInserted,
    tripsUpdated: trips.counts.tripsUpdated,
    tripsUnchanged: trips.counts.tripsUnchanged,
    warnings: [...visits.counts.warnings, ...states.counts.warnings, ...trips.counts.warnings],
  };
}

export async function exportDiary(): Promise<Diary> {
  const diary = await buildDiary();
  const activeCount = diary.visits.filter((visit) => !visit.deleted_at).length;
  await setMeta("last_diary_export_at", diary.exported_at);
  await setMeta("visits_at_last_export", activeCount);
  await persistStorage();
  return diary;
}

export async function loadDiaryMeta(): Promise<DiaryMeta> {
  const [last_export_at, last_import_at, visits_at_last_export] = await Promise.all([
    metaValue<string>("last_diary_export_at"),
    metaValue<string>("last_diary_import_at"),
    metaValue<number>("visits_at_last_export"),
  ]);
  return {
    last_export_at: last_export_at ?? null,
    last_import_at: last_import_at ?? null,
    visits_at_last_export: visits_at_last_export ?? 0,
  };
}

function fallbackDownload(blob: Blob): void {
  if (typeof document === "undefined") {
    return;
  }
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "diary.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function downloadDiaryFile(diary: Diary): Promise<void> {
  const blob = new Blob([`${JSON.stringify(diary, null, 2)}\n`], { type: "application/json;charset=utf-8" });
  const file = new File([blob], "diary.json", { type: "application/json" });
  if (typeof navigator !== "undefined") {
    const nav = navigator as Navigator & {
      canShare?: (data: ShareData) => boolean;
      share?: (data: ShareData) => Promise<void>;
    };
    if (typeof nav.share === "function") {
      const payload: ShareData = { files: [file], title: "diary.json", text: "Záloha deníku Památky" };
      let canShareFiles = true;
      if (typeof nav.canShare === "function") {
        try {
          canShareFiles = nav.canShare(payload);
        } catch {
          canShareFiles = false;
        }
      }
      if (canShareFiles) {
        try {
          await nav.share(payload);
          return;
        } catch (err) {
          if (err instanceof DOMException && err.name === "AbortError") {
            return;
          }
        }
      }
    }
  }
  fallbackDownload(blob);
}
