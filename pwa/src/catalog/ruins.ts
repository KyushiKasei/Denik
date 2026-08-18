import type { CatalogPlace, PlaceTypeCode } from "./types";

/** Typ zřícenina nebo fyzický stav zřícenina — stejné jako kolekce Dnes. */
export function isRuin(place: CatalogPlace): boolean {
  return place.types.includes("RUIN") || place.condition === "RUIN";
}

export function placeMatchesType(place: CatalogPlace, type: PlaceTypeCode): boolean {
  if (type === "RUIN") {
    return isRuin(place);
  }
  return place.types.includes(type);
}
