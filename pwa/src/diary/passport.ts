import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { CZECH_REGIONS, matchCzechRegion, type CzechRegion } from "./regions";
import { stampArtForPlace, type StampKind } from "./stampArt";

export interface PassportStamp {
  placeId: string;
  visitId: string;
  name: string;
  visitedAt: string | null;
  kind: StampKind;
  wax: string;
}

export interface PassportPage {
  region: CzechRegion;
  visited: number;
  total: number;
  stamps: PassportStamp[];
  emptySlots: number;
}

const MAX_EMPTY_SLOTS = 6;

export function passportPages(
  places: CatalogPlace[],
  visits: StoredVisit[],
  snapshots: Map<string, { name: string }> = new Map(),
): PassportPage[] {
  const placesById = new Map(places.map((place) => [place.id, place]));
  const totals = new Map<string, number>();
  const stampsByRegion = new Map<string, PassportStamp[]>();
  for (const region of CZECH_REGIONS) {
    totals.set(region.id, 0);
    stampsByRegion.set(region.id, []);
  }

  for (const place of places) {
    const region = matchCzechRegion(place.location.region);
    if (!region) {
      continue;
    }
    totals.set(region.id, (totals.get(region.id) ?? 0) + 1);
  }

  const seenPlace = new Set<string>();
  const live = visits
    .filter((visit) => !visit.deleted_at)
    .sort(
      (a, b) =>
        (a.visited_at ?? "").localeCompare(b.visited_at ?? "") || a.created_at.localeCompare(b.created_at),
    );

  for (const visit of live) {
    if (seenPlace.has(visit.place_id)) {
      continue;
    }
    seenPlace.add(visit.place_id);
    const place = placesById.get(visit.place_id);
    const region = matchCzechRegion(place?.location.region);
    if (!region) {
      continue;
    }
    const art = stampArtForPlace(place);
    stampsByRegion.get(region.id)?.push({
      placeId: visit.place_id,
      visitId: visit.id,
      name: place?.name ?? snapshots.get(visit.place_id)?.name ?? "Místo",
      visitedAt: visit.visited_at,
      kind: art.kind,
      wax: art.wax,
    });
  }

  return CZECH_REGIONS.map((region) => {
    const stamps = stampsByRegion.get(region.id) ?? [];
    const total = totals.get(region.id) ?? 0;
    const remaining = Math.max(0, total - stamps.length);
    return {
      region,
      visited: stamps.length,
      total,
      stamps,
      emptySlots: Math.min(MAX_EMPTY_SLOTS, remaining),
    };
  });
}

export function pageForRegion(pages: PassportPage[], regionId: string | null): PassportPage | null {
  if (!regionId) {
    return pages.find((page) => page.stamps.length > 0) ?? pages[0] ?? null;
  }
  return pages.find((page) => page.region.id === regionId) ?? null;
}
