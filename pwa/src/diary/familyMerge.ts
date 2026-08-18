import type { StoredPlaceState, StoredVisit } from "../catalog/types";
import { nowIso } from "./ids";
import { MAX_PHOTOS_PER_VISIT } from "./photos";
import type { StoredVisitPhoto } from "./types";

export function mergePeople(left: string[], right: string[]): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const name of [...left, ...right]) {
    const trimmed = name.trim();
    if (!trimmed) {
      continue;
    }
    const key = trimmed.toLocaleLowerCase("cs");
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    names.push(trimmed);
  }
  return names;
}

export function mergeNotes(left: string | null | undefined, right: string | null | undefined): string | null {
  const a = (left || "").trim();
  const b = (right || "").trim();
  if (a && b && a.toLocaleLowerCase("cs") !== b.toLocaleLowerCase("cs")) {
    return `${a} · ${b}`;
  }
  return a || b || null;
}

function richness(visit: StoredVisit, photoCounts: ReadonlyMap<string, number>): number {
  let score = 0;
  if ((visit.note || "").trim()) {
    score += 2;
  }
  if (visit.rating) {
    score += 1;
  }
  score += Math.min(3, visit.people.length);
  score += Math.min(3, photoCounts.get(visit.id) ?? 0);
  return score;
}

export function collapseFamilyVisits(
  visits: StoredVisit[],
  photoCounts: ReadonlyMap<string, number> = new Map(),
): { next: StoredVisit[]; collapsed: number; photoMoves: Array<{ from: string; to: string }> } {
  const groups = new Map<string, StoredVisit[]>();
  for (const visit of visits) {
    if (visit.deleted_at) {
      continue;
    }
    const day = (visit.visited_at || "").trim();
    if (!day) {
      continue;
    }
    const key = `${visit.place_id}|${day}`;
    const rows = groups.get(key) ?? [];
    rows.push(visit);
    groups.set(key, rows);
  }
  const byId = new Map(visits.map((visit) => [visit.id, { ...visit }]));
  let collapsed = 0;
  const photoMoves: Array<{ from: string; to: string }> = [];
  const stamp = nowIso();
  for (const rows of groups.values()) {
    if (rows.length < 2) {
      continue;
    }
    const ranked = [...rows].sort(
      (a, b) =>
        richness(b, photoCounts) - richness(a, photoCounts) ||
        b.created_at.localeCompare(a.created_at) ||
        a.id.localeCompare(b.id),
    );
    const winnerId = ranked[0]?.id;
    if (!winnerId) {
      continue;
    }
    const winner = byId.get(winnerId);
    if (!winner) {
      continue;
    }
    for (const loser of ranked.slice(1)) {
      const current = byId.get(loser.id);
      if (!current) {
        continue;
      }
      winner.people = mergePeople(winner.people, current.people);
      winner.note = mergeNotes(winner.note, current.note);
      if (current.rating != null && (winner.rating == null || current.rating > winner.rating)) {
        winner.rating = current.rating;
      }
      if (current.trip_id && !winner.trip_id) {
        winner.trip_id = current.trip_id;
      }
      current.deleted_at = stamp;
      current.updated_at = stamp;
      photoMoves.push({ from: loser.id, to: winnerId });
      collapsed += 1;
    }
    winner.updated_at = stamp;
    byId.set(winnerId, winner);
  }
  return { next: [...byId.values()], collapsed, photoMoves };
}

export function unionFamilyStates(local: StoredPlaceState[], incoming: StoredPlaceState[]): StoredPlaceState[] {
  const byId = new Map(local.map((state) => [state.place_id, { ...state }]));
  const stamp = nowIso();
  for (const item of incoming) {
    const existing = byId.get(item.place_id);
    if (!existing) {
      byId.set(item.place_id, item);
      continue;
    }
    existing.want_to_visit = existing.want_to_visit || item.want_to_visit;
    existing.favorite = existing.favorite || item.favorite;
    existing.personal_note = mergeNotes(existing.personal_note, item.personal_note);
    existing.deleted_at = null;
    existing.updated_at = stamp;
    byId.set(item.place_id, existing);
  }
  return [...byId.values()];
}

export function reassignPhotos(
  photos: StoredVisitPhoto[],
  moves: Array<{ from: string; to: string }>,
): StoredVisitPhoto[] {
  const map = new Map(moves.map((row) => [row.from, row.to]));
  const counts = new Map<string, number>();
  const kept: StoredVisitPhoto[] = [];
  const moved: StoredVisitPhoto[] = [];
  for (const photo of photos) {
    const nextVisit = map.get(photo.visit_id);
    if (nextVisit) {
      moved.push({ ...photo, visit_id: nextVisit });
      continue;
    }
    const n = counts.get(photo.visit_id) ?? 0;
    if (n >= MAX_PHOTOS_PER_VISIT) {
      continue;
    }
    counts.set(photo.visit_id, n + 1);
    kept.push(photo);
  }
  for (const photo of moved) {
    const n = counts.get(photo.visit_id) ?? 0;
    if (n >= MAX_PHOTOS_PER_VISIT) {
      continue;
    }
    counts.set(photo.visit_id, n + 1);
    kept.push(photo);
  }
  return kept;
}
