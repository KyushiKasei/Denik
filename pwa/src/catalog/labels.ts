import enums from "@shared/enums.json";
import type { CatalogPlace, PlaceTypeCode } from "./types";

const typeLabels = new Map(enums.place_types.map((item) => [item.code, item.name_cs]));
const conditionLabels = new Map(enums.condition.map((item) => [item.code, item.name_cs]));
const visitabilityLabels = new Map(enums.visitability.map((item) => [item.code, item.name_cs]));
const heritageLabels = new Map(enums.heritage_status.map((item) => [item.code, item.name_cs]));

export const PLACE_TYPE_OPTIONS = enums.place_types.map((item) => ({
  code: item.code as PlaceTypeCode,
  name_cs: item.name_cs,
}));

export const VISITABILITY_OPTIONS = enums.visitability.map((item) => ({
  code: item.code,
  name_cs: item.name_cs,
}));

export const VISITABILITY_FILTER_GROUPS = enums.visitability_filter_groups.map((item) => ({
  code: item.code as "PUBLIC" | "NOT_PUBLIC",
  name_cs: item.name_cs,
  codes: item.codes,
}));

export const HERITAGE_OPTIONS = enums.heritage_status.map((item) => ({
  code: item.code,
  name_cs: item.name_cs,
}));

export function visitabilityMatches(placeCode: string, filter: string): boolean {
  if (!filter) {
    return true;
  }
  const group = VISITABILITY_FILTER_GROUPS.find((item) => item.code === filter);
  if (group) {
    return group.codes.includes(placeCode);
  }
  return placeCode === filter;
}

export function typeLabel(code: string): string {
  return typeLabels.get(code) ?? code;
}

export function formatTypes(types: string[]): string {
  if (types.length === 0) {
    return "Bez typu";
  }
  const names = types.map(typeLabel);
  if (names.length === 2) {
    return `${names[0]} a ${names[1].toLocaleLowerCase("cs")}`;
  }
  return names.join(", ");
}

export function conditionLabel(code: string): string {
  return conditionLabels.get(code) ?? code;
}

export function visitabilityLabel(code: string): string {
  return visitabilityLabels.get(code) ?? code;
}

export function heritageLabel(code: string | null): string {
  if (!code) {
    return "—";
  }
  return heritageLabels.get(code) ?? code;
}

export function hasGps(place: CatalogPlace): boolean {
  return place.location.latitude != null && place.location.longitude != null;
}

export function formatGps(place: CatalogPlace): string | null {
  if (!hasGps(place)) {
    return null;
  }
  return `${place.location.latitude}, ${place.location.longitude}`;
}

export function mapyCzUrl(place: CatalogPlace): string | null {
  const gps = formatGps(place);
  return gps ? `https://mapy.cz/zakladni?q=${encodeURIComponent(gps)}` : null;
}

export function googleMapsUrl(place: CatalogPlace): string | null {
  const gps = formatGps(place);
  return gps ? `https://www.google.com/maps?q=${encodeURIComponent(gps)}` : null;
}

export function appleMapsUrl(place: CatalogPlace): string | null {
  if (!hasGps(place) || place.location.latitude == null || place.location.longitude == null) {
    return null;
  }
  const q = encodeURIComponent(place.name);
  return `https://maps.apple.com/?ll=${place.location.latitude},${place.location.longitude}&q=${q}`;
}

export function locationLine(place: CatalogPlace): string {
  const parts = [place.location.municipality, place.location.district, place.location.region].filter(
    (part): part is string => Boolean(part),
  );
  return parts.join(" · ");
}
