import regionsPayload from "@shared/czech-regions.json";
import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { isRuin } from "../catalog/ruins";
import { fold } from "../text/fold";
import { uniqueVisitedPlaceIds } from "./timeline";

export interface CzechRegion {
  id: string;
  name: string;
  short: string;
  path: string;
}

/** Schematická mapa 14 krajů (vlastní kresba, ne oficiální hranice). */
export const CZECH_REGIONS: CzechRegion[] = regionsPayload.regions;

function regionKey(value: string): string {
  return fold(value)
    .replace(/\bhlavni mesto\b/g, "")
    .replace(/\bkraj\b/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

const REGION_BY_KEY = new Map<string, CzechRegion>();
for (const region of CZECH_REGIONS) {
  REGION_BY_KEY.set(regionKey(region.name), region);
  REGION_BY_KEY.set(regionKey(region.short), region);
  REGION_BY_KEY.set(regionKey(region.id), region);
}
REGION_BY_KEY.set("praha", CZECH_REGIONS.find((row) => row.id === "PHA")!);
REGION_BY_KEY.set("vysocina", CZECH_REGIONS.find((row) => row.id === "VYS")!);

export function matchCzechRegion(raw: string | null | undefined): CzechRegion | null {
  if (!raw?.trim()) {
    return null;
  }
  return REGION_BY_KEY.get(regionKey(raw)) ?? null;
}

export interface RegionProgress {
  region: CzechRegion;
  visited: number;
  total: number;
  unlocked: boolean;
}

export function regionProgress(places: CatalogPlace[], visits: StoredVisit[]): RegionProgress[] {
  const visitedIds = uniqueVisitedPlaceIds(visits);
  const totals = new Map<string, number>();
  const visited = new Map<string, number>();
  for (const region of CZECH_REGIONS) {
    totals.set(region.id, 0);
    visited.set(region.id, 0);
  }
  for (const place of places) {
    const region = matchCzechRegion(place.location.region);
    if (!region) {
      continue;
    }
    totals.set(region.id, (totals.get(region.id) ?? 0) + 1);
    if (visitedIds.has(place.id)) {
      visited.set(region.id, (visited.get(region.id) ?? 0) + 1);
    }
  }
  return CZECH_REGIONS.map((region) => {
    const seen = visited.get(region.id) ?? 0;
    return {
      region,
      visited: seen,
      total: totals.get(region.id) ?? 0,
      unlocked: seen > 0,
    };
  });
}

export function unlockedRegionCount(rows: RegionProgress[]): number {
  return rows.filter((row) => row.unlocked).length;
}

export interface CollectionStat {
  id: "nkp" | "unesco" | "ruin";
  title: string;
  visited: number;
  total: number;
}

export function collectionStats(places: CatalogPlace[], visits: StoredVisit[]): CollectionStat[] {
  const visitedIds = uniqueVisitedPlaceIds(visits);
  const nkp = places.filter((place) => place.heritage_status === "NKP");
  const unesco = places.filter((place) => place.unesco);
  const ruins = places.filter(isRuin);
  const countVisited = (rows: CatalogPlace[]) => rows.filter((place) => visitedIds.has(place.id)).length;
  return [
    { id: "nkp", title: "NKP", visited: countVisited(nkp), total: nkp.length },
    { id: "unesco", title: "UNESCO", visited: countVisited(unesco), total: unesco.length },
    { id: "ruin", title: "Zříceniny", visited: countVisited(ruins), total: ruins.length },
  ];
}
