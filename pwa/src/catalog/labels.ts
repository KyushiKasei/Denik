import enums from "@shared/enums.json";
import type { CatalogPlace, PlaceTypeCode } from "./types";
import { fold } from "../text/fold";

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

export const CONDITION_OPTIONS = enums.condition.map((item) => ({
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

export function formatTypes(types: string[], options?: { omitLabels?: string[]; hideInName?: string }): string {
  if (types.length === 0) {
    return "Bez typu";
  }
  const omit = new Set((options?.omitLabels ?? []).map((label) => fold(label)));
  const nameFold = options?.hideInName ? fold(options.hideInName) : "";
  const names = [...new Set(types.map(typeLabel))].filter((label) => {
    const key = fold(label);
    if (omit.has(key)) {
      return false;
    }
    if (nameFold && nameFold.includes(key)) {
      return false;
    }
    return true;
  });
  if (names.length === 0) {
    return "";
  }
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
  const parts: string[] = [];
  for (const part of [place.location.municipality, place.location.district, place.location.region]) {
    if (!part) {
      continue;
    }
    if (parts.some((seen) => redundantLocationPart(part, seen))) {
      continue;
    }
    parts.push(part);
  }
  return parts.join(" · ");
}

function normalizeLocation(value: string): string {
  return fold(value)
    .replace(/\buzemi\b/g, " ")
    .replace(/\bhlavni(ho)?\b/g, " ")
    .replace(/\bmest[ao]\b/g, " ")
    .replace(/\bprahy\b/g, "praha")
    .replace(/\s+/g, " ")
    .trim();
}

function redundantLocationPart(current: string, seen: string): boolean {
  const a = normalizeLocation(current);
  const b = normalizeLocation(seen);
  if (!a || !b) {
    return false;
  }
  if (a === b) {
    return true;
  }
  const longer = a.length >= b.length ? a : b;
  const shorter = a.length >= b.length ? b : a;
  return shorter.length >= 4 && longer.includes(shorter);
}

export function displayPlaceName(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) {
    return name;
  }
  const first = trimmed[0] ?? "";
  const upper = first.toLocaleUpperCase("cs");
  if (first === upper) {
    return trimmed;
  }
  return `${upper}${trimmed.slice(1)}`;
}

export function isInternalReviewNote(text: string | null | undefined): boolean {
  const raw = (text || "").trim();
  if (!raw) {
    return false;
  }
  const folded = fold(raw);
  return folded.includes("pro review") || folded.includes("nejasny zaznam");
}

export function publicDescription(place: CatalogPlace): string | null {
  const text = (place.short_description || "").trim();
  if (!text || isInternalReviewNote(text)) {
    return null;
  }
  return text;
}

const FEE_LABELS: Record<string, string> = {
  yes: "vstupné",
  no: "zdarma",
  donation: "dobrovolné",
  customers: "pro návštěvníky",
};

const WHEELCHAIR_LABELS: Record<string, string> = {
  yes: "bezbariérové",
  limited: "částečně bezbariérové",
  no: "není bezbariérové",
  designated: "vyhrazený přístup",
};

const PARKING_LABELS: Record<string, string> = {
  yes: "parkování",
  no: "bez parkování",
  surface: "parkování",
  lane: "parkování u silnice",
};

function normalizeTag(value: string | null | undefined): string {
  return (value || "").trim().toLowerCase();
}

export function feeLabel(value: string | null | undefined): string | null {
  const key = normalizeTag(value);
  if (!key) {
    return null;
  }
  return FEE_LABELS[key] ?? value!.trim();
}

export function wheelchairLabel(value: string | null | undefined): string | null {
  const key = normalizeTag(value);
  if (!key) {
    return null;
  }
  return WHEELCHAIR_LABELS[key] ?? value!.trim();
}

export function parkingLabel(value: string | null | undefined): string | null {
  const key = normalizeTag(value);
  if (!key) {
    return null;
  }
  return PARKING_LABELS[key] ?? `parkování: ${value!.trim()}`;
}

export function phoneHref(value: string | null | undefined): string | null {
  const raw = (value || "").trim();
  if (!raw) {
    return null;
  }
  const digits = raw.replace(/[^\d+]/g, "");
  return digits ? `tel:${digits}` : null;
}

const DOGS_LABELS: Record<string, string> = {
  yes: "psi ano",
  no: "psi ne",
  leashed: "psi na vodítku",
  outside: "psi venku",
};

const PAYMENT_LABELS: Record<string, string> = {
  cash: "hotově",
  cards: "kartou",
  cash_and_cards: "hotově i kartou",
};

const AMENITY_LABELS: Record<string, string> = {
  toilets: "toalety",
  cafe: "občerstvení",
  playground: "hřiště",
};

export function dogsLabel(value: string | null | undefined): string | null {
  const key = normalizeTag(value);
  if (!key) {
    return null;
  }
  return DOGS_LABELS[key] ?? value!.trim();
}

export function paymentLabel(value: string | null | undefined): string | null {
  const key = normalizeTag(value);
  if (!key || key === "unknown") {
    return null;
  }
  return PAYMENT_LABELS[key] ?? value!.trim();
}

export function amenitiesLine(place: CatalogPlace): string | null {
  const codes = place.amenities ?? [];
  if (codes.length === 0) {
    return null;
  }
  return codes.map((code) => AMENITY_LABELS[code] ?? code).join(" · ");
}

export function styleLine(place: CatalogPlace): string | null {
  const style = (place.architectural_style || "").trim();
  const year = place.inception_year;
  const century = year != null && year >= 100 ? `${Math.ceil(year / 100)}. stol.` : null;
  const parts = [style || null, century].filter((part): part is string => Boolean(part));
  return parts.length ? parts.join(" · ") : null;
}

export function hasAmenity(place: CatalogPlace, code: "toilets" | "cafe" | "playground"): boolean {
  return (place.amenities ?? []).includes(code);
}
