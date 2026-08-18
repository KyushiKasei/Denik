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
export const CZECH_REGIONS: CzechRegion[] = [
  {
    id: "KVK",
    name: "Karlovarský kraj",
    short: "KVK",
    path: "M 40,180 L 145,118 205,165 178,262 88,292 38,228 Z",
  },
  {
    id: "ULK",
    name: "Ústecký kraj",
    short: "ULK",
    path: "M 145,118 L 285,68 385,92 402,172 278,202 205,165 Z",
  },
  {
    id: "LBK",
    name: "Liberecký kraj",
    short: "LBK",
    path: "M 385,92 L 525,52 585,112 522,178 402,172 Z",
  },
  {
    id: "PLK",
    name: "Plzeňský kraj",
    short: "PLK",
    path: "M 88,292 L 178,262 252,305 278,425 158,482 68,398 58,322 Z",
  },
  {
    id: "STC",
    name: "Středočeský kraj",
    short: "STČ",
    path: "M 205,165 L 402,172 522,178 562,224 582,322 478,382 318,402 252,305 178,262 278,202 Z",
  },
  {
    id: "PHA",
    name: "Hlavní město Praha",
    short: "PHA",
    path: "M 412,232 L 462,222 488,252 456,282 408,270 Z",
  },
  {
    id: "JHC",
    name: "Jihočeský kraj",
    short: "JHČ",
    path: "M 252,305 L 318,402 478,382 542,452 428,532 248,522 158,482 278,425 Z",
  },
  {
    id: "HKK",
    name: "Královéhradecký kraj",
    short: "HKK",
    path: "M 522,178 L 585,112 725,98 785,172 702,232 562,224 Z",
  },
  {
    id: "PAK",
    name: "Pardubický kraj",
    short: "PAK",
    path: "M 562,224 L 702,232 785,172 822,252 742,312 582,322 Z",
  },
  {
    id: "VYS",
    name: "Kraj Vysočina",
    short: "VYS",
    path: "M 478,382 L 582,322 742,312 782,382 682,452 542,452 Z",
  },
  {
    id: "OLK",
    name: "Olomoucký kraj",
    short: "OLK",
    path: "M 702,232 L 785,172 885,188 922,272 842,332 742,312 822,252 Z",
  },
  {
    id: "MSK",
    name: "Moravskoslezský kraj",
    short: "MSK",
    path: "M 785,172 L 885,118 982,158 992,252 922,272 885,188 Z",
  },
  {
    id: "ZLK",
    name: "Zlínský kraj",
    short: "ZLK",
    path: "M 742,312 L 842,332 922,272 992,252 972,362 858,422 782,382 Z",
  },
  {
    id: "JHM",
    name: "Jihomoravský kraj",
    short: "JHM",
    path: "M 542,452 L 682,452 782,382 858,422 838,512 678,552 428,532 Z",
  },
];

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
