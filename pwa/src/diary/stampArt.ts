import art from "@shared/stamp-art.json";
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

const KIND_BY_TYPE = art.kind_by_type as Partial<Record<PlaceTypeCode, StampKind>>;
const TYPE_PRIORITY = art.type_priority as PlaceTypeCode[];

export const REGION_WAX: Record<string, string> = art.region_wax;
export const DEFAULT_WAX = art.default_wax;
export const WANT_WAX = art.want_wax;
export const STAMP_PATHS = art.stamp_paths as Record<StampKind, string>;

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
