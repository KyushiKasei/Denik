import type { CatalogPlace } from "../catalog/types";
import { hasGps } from "../catalog/labels";
import { appliedSearchQuery, fold } from "../text/fold";

export const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";

export interface GeoOrigin {
  latitude: number;
  longitude: number;
  label: string;
  source: "coords" | "place" | "municipality" | "nominatim" | "gps";
}

export function suggestOrigins(places: CatalogPlace[], q: string, limit = 8): GeoOrigin[] {
  const term = fold(appliedSearchQuery(q));
  if (!term) {
    return [];
  }
  const out: GeoOrigin[] = [];
  for (const place of places) {
    if (!hasGps(place) || place.location.latitude == null || place.location.longitude == null) {
      continue;
    }
    const hay = fold(
      [place.name, place.short_name ?? "", place.location.municipality ?? "", ...place.alternative_names].join(" "),
    );
    if (!hay.includes(term)) {
      continue;
    }
    out.push({
      latitude: place.location.latitude,
      longitude: place.location.longitude,
      label: place.name,
      source: "place",
    });
    if (out.length >= limit) {
      break;
    }
  }
  return out;
}

export function resolveOriginFromCatalog(places: CatalogPlace[], q: string): GeoOrigin | null {
  const needle = fold(q.trim());
  if (!needle) {
    return null;
  }
  const withGps = places.filter(
    (place): place is CatalogPlace & { location: CatalogPlace["location"] & { latitude: number; longitude: number } } =>
      hasGps(place) && place.location.latitude != null && place.location.longitude != null,
  );

  const exactName = withGps.filter((place) => fold(place.name) === needle);
  if (exactName[0]) {
    const place = exactName[0];
    return { latitude: place.location.latitude, longitude: place.location.longitude, label: place.name, source: "place" };
  }

  const exactMuni = withGps.filter((place) => fold(place.location.municipality ?? "") === needle);
  if (exactMuni[0]) {
    const place = exactMuni[0];
    return {
      latitude: place.location.latitude,
      longitude: place.location.longitude,
      label: place.location.municipality || place.name,
      source: "municipality",
    };
  }

  const starts = withGps.filter((place) => fold(place.name).startsWith(needle));
  if (starts[0]) {
    const place = starts[0];
    return { latitude: place.location.latitude, longitude: place.location.longitude, label: place.name, source: "place" };
  }

  const contains = withGps.filter((place) => fold(place.name).includes(needle));
  if (contains[0]) {
    const place = contains[0];
    return { latitude: place.location.latitude, longitude: place.location.longitude, label: place.name, source: "place" };
  }

  return null;
}

export async function geocodeNominatim(q: string): Promise<GeoOrigin | null> {
  const term = q.trim();
  if (term.length < 2) {
    return null;
  }
  const url = new URL(NOMINATIM_URL);
  url.searchParams.set("q", term);
  url.searchParams.set("format", "json");
  url.searchParams.set("limit", "1");
  url.searchParams.set("countrycodes", "cz");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15_000);
  try {
    const response = await fetch(url.toString(), {
      headers: { Accept: "application/json", "Accept-Language": "cs" },
      signal: controller.signal,
    });
    if (!response.ok) {
      return null;
    }
    const data: unknown = await response.json();
    if (!Array.isArray(data) || data.length === 0 || typeof data[0] !== "object" || data[0] == null) {
      return null;
    }
    const row = data[0] as { lat?: string; lon?: string; display_name?: string };
    const latitude = Number(row.lat);
    const longitude = Number(row.lon);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      return null;
    }
    return {
      latitude,
      longitude,
      label: row.display_name || term,
      source: "nominatim",
    };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
