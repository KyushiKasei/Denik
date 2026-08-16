import type { StoredPlaceState, StoredVisit } from "../catalog/types";
import type { DiaryMergeCounts, StoredTrip } from "./types";

function parseTimestamp(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms;
}

export function incomingIsNewer(incomingAt: string | null | undefined, localAt: string | null | undefined): {
  apply: boolean;
  tied: boolean;
} {
  const incoming = parseTimestamp(incomingAt);
  const local = parseTimestamp(localAt);
  if (incoming == null && local == null) {
    return { apply: true, tied: true };
  }
  if (incoming == null) {
    return { apply: false, tied: false };
  }
  if (local == null) {
    return { apply: true, tied: false };
  }
  if (incoming > local) {
    return { apply: true, tied: false };
  }
  if (incoming < local) {
    return { apply: false, tied: false };
  }
  return { apply: true, tied: true };
}

function visitEqual(local: StoredVisit, incoming: StoredVisit): boolean {
  return (
    local.place_id === incoming.place_id &&
    local.visited_at === incoming.visited_at &&
    local.rating === incoming.rating &&
    JSON.stringify(local.people) === JSON.stringify(incoming.people) &&
    (local.note ?? null) === (incoming.note ?? null) &&
    (local.deleted_at ?? null) === (incoming.deleted_at ?? null) &&
    local.created_at === incoming.created_at &&
    local.updated_at === incoming.updated_at
  );
}

function stateEqual(local: StoredPlaceState, incoming: StoredPlaceState): boolean {
  return (
    local.want_to_visit === incoming.want_to_visit &&
    local.favorite === incoming.favorite &&
    (local.personal_note ?? null) === (incoming.personal_note ?? null) &&
    (local.deleted_at ?? null) === (incoming.deleted_at ?? null) &&
    local.updated_at === incoming.updated_at
  );
}

export function mergeVisits(local: StoredVisit[], incoming: StoredVisit[]): {
  next: StoredVisit[];
  counts: Pick<DiaryMergeCounts, "visitsInserted" | "visitsUpdated" | "visitsUnchanged" | "warnings">;
} {
  const byId = new Map(local.map((visit) => [visit.id, visit]));
  let visitsInserted = 0;
  let visitsUpdated = 0;
  let visitsUnchanged = 0;
  const warnings: string[] = [];

  for (const item of incoming) {
    const existing = byId.get(item.id);
    if (!existing) {
      byId.set(item.id, item);
      visitsInserted += 1;
      continue;
    }
    const { apply, tied } = incomingIsNewer(item.updated_at, existing.updated_at);
    if (!apply) {
      visitsUnchanged += 1;
      continue;
    }
    if (tied && visitEqual(existing, item)) {
      visitsUnchanged += 1;
      continue;
    }
    if (tied) {
      warnings.push(`Návštěva ${item.id}: stejný updated_at, použita příchozí hodnota.`);
    }
    byId.set(item.id, item);
    visitsUpdated += 1;
  }

  return {
    next: [...byId.values()],
    counts: { visitsInserted, visitsUpdated, visitsUnchanged, warnings },
  };
}

export function mergePlaceStates(local: StoredPlaceState[], incoming: StoredPlaceState[]): {
  next: StoredPlaceState[];
  counts: Pick<DiaryMergeCounts, "statesInserted" | "statesUpdated" | "statesUnchanged" | "warnings">;
} {
  const byId = new Map(local.map((state) => [state.place_id, state]));
  let statesInserted = 0;
  let statesUpdated = 0;
  let statesUnchanged = 0;
  const warnings: string[] = [];

  for (const item of incoming) {
    const existing = byId.get(item.place_id);
    if (!existing) {
      byId.set(item.place_id, item);
      statesInserted += 1;
      continue;
    }
    const { apply, tied } = incomingIsNewer(item.updated_at, existing.updated_at);
    if (!apply) {
      statesUnchanged += 1;
      continue;
    }
    if (tied && stateEqual(existing, item)) {
      statesUnchanged += 1;
      continue;
    }
    if (tied) {
      warnings.push(`Stav místa ${item.place_id}: stejný updated_at, použita příchozí hodnota.`);
    }
    byId.set(item.place_id, item);
    statesUpdated += 1;
  }

  return {
    next: [...byId.values()],
    counts: { statesInserted, statesUpdated, statesUnchanged, warnings },
  };
}

function tripEqual(local: StoredTrip, incoming: StoredTrip): boolean {
  return JSON.stringify(local) === JSON.stringify(incoming);
}

export function mergeTrips(local: StoredTrip[], incoming: StoredTrip[]): {
  next: StoredTrip[];
  counts: Pick<DiaryMergeCounts, "tripsInserted" | "tripsUpdated" | "tripsUnchanged" | "warnings">;
} {
  const byId = new Map(local.map((trip) => [trip.id, trip]));
  let tripsInserted = 0;
  let tripsUpdated = 0;
  let tripsUnchanged = 0;
  const warnings: string[] = [];

  for (const item of incoming) {
    const existing = byId.get(item.id);
    if (!existing) {
      byId.set(item.id, item);
      tripsInserted += 1;
      continue;
    }
    const { apply, tied } = incomingIsNewer(item.updated_at, existing.updated_at);
    if (!apply) {
      tripsUnchanged += 1;
      continue;
    }
    if (tied && tripEqual(existing, item)) {
      tripsUnchanged += 1;
      continue;
    }
    if (tied) {
      warnings.push(`Výlet ${item.id}: stejný updated_at, použita příchozí hodnota.`);
    }
    byId.set(item.id, item);
    tripsUpdated += 1;
  }

  return {
    next: [...byId.values()],
    counts: { tripsInserted, tripsUpdated, tripsUnchanged, warnings },
  };
}
