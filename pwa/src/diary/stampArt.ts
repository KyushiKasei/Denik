import type { CatalogPlace, PlaceTypeCode } from "../catalog/types";
import { matchCzechRegion } from "./regions";

export type StampKind =
  | "castle"
  | "chateau"
  | "ruin"
  | "fortress"
  | "manor"
  | "palace"
  | "tower"
  | "zoo"
  | "cave"
  | "other";

const KIND_BY_TYPE: Partial<Record<PlaceTypeCode, StampKind>> = {
  RUIN: "ruin",
  CASTLE: "castle",
  CHATEAU: "chateau",
  FORTRESS: "fortress",
  MANOR: "manor",
  PALACE: "palace",
  LOOKOUT_TOWER: "tower",
  ZOO: "zoo",
  CAVE: "cave",
  OTHER: "other",
};

const TYPE_PRIORITY: PlaceTypeCode[] = [
  "RUIN",
  "CASTLE",
  "CHATEAU",
  "FORTRESS",
  "MANOR",
  "PALACE",
  "LOOKOUT_TOWER",
  "ZOO",
  "CAVE",
  "OTHER",
];

/** Voskové barvy podle kraje — čitelné na papíru i ve tmě. */
export const REGION_WAX: Record<string, string> = {
  KVK: "#8a3d2c",
  ULK: "#3d5a40",
  LBK: "#2f5f73",
  PLK: "#6b4a2e",
  STC: "#4a5c38",
  PHA: "#8b2e2e",
  JHC: "#3d4f7a",
  HKK: "#6a3d5c",
  PAK: "#5a6b2e",
  VYS: "#7a5a28",
  OLK: "#2e5a4a",
  MSK: "#5a3d2e",
  ZLK: "#4a3d6b",
  JHM: "#7a3d4a",
};

export const DEFAULT_WAX = "#3d5a40";
export const WANT_WAX = "#c9a227";

export function stampKindFromTypes(types: PlaceTypeCode[]): StampKind {
  for (const type of TYPE_PRIORITY) {
    if (types.includes(type) && KIND_BY_TYPE[type]) {
      return KIND_BY_TYPE[type]!;
    }
  }
  return "other";
}

export function waxColorForRegion(raw: string | null | undefined): string {
  const region = matchCzechRegion(raw);
  if (!region) {
    return DEFAULT_WAX;
  }
  return REGION_WAX[region.id] ?? DEFAULT_WAX;
}

export function stampArtForPlace(place: CatalogPlace | null | undefined): { kind: StampKind; wax: string } {
  if (!place) {
    return { kind: "other", wax: DEFAULT_WAX };
  }
  return {
    kind: stampKindFromTypes(place.types),
    wax: waxColorForRegion(place.location.region),
  };
}

/** Jednoduché siluety 64×64, kreslené jako otisk. */
export const STAMP_PATHS: Record<StampKind, string> = {
  castle: "M8 52h48V28l-8-8h-8v-8h-8v8h-8V12h-8v8H16l-8 8z M20 52V36h8v16h8V36h8v16",
  chateau: "M6 50h52V30L32 12 6 30z M16 50V36h10v14h12V36h10v14",
  ruin: "M8 52h48V34l-10-14h-8v10l-8-12h-10v16H8z M28 52V40h8v12",
  fortress: "M32 10 54 28v24H10V28z M22 52V36h20v16",
  manor: "M8 50h48V32L32 14 8 32z M24 50V38h16v12",
  palace: "M4 50h56V28H4z M10 28V16h8v12h8V16h8v12h8V16h8v12",
  tower: "M26 54h12V22l-6-12-6 12z M22 54h20",
  zoo: "M18 44c0-10 28-10 28 0v8H18z M24 28c0-6 16-6 16 0",
  cave: "M8 52c0-20 16-36 24-36s24 16 24 36z M20 52c4-12 20-12 24 0",
  other: "M32 12 52 32 32 52 12 32z",
};
