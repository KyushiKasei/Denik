import { clampRadiusKm, DEFAULT_RADIUS_KM } from "./haversine";
import type { GeoOrigin } from "./origin";

/** Klíč jen pro Mapu. Záložka Deník (wave 3) sem nesmí sahat. */
export const MAP_LAST_ORIGIN_KEY = "pamatky.map.lastOrigin";

export interface StoredMapView {
  latitude: number;
  longitude: number;
  label: string;
  source?: GeoOrigin["source"];
  radiusKm: number;
}

const ORIGIN_SOURCES: GeoOrigin["source"][] = ["coords", "place", "municipality", "nominatim", "gps"];

export function urlHasCoords(params: URLSearchParams): boolean {
  const latRaw = params.get("lat");
  const lonRaw = params.get("lon");
  if (!latRaw || !lonRaw) {
    return false;
  }
  const lat = Number(latRaw);
  const lon = Number(lonRaw);
  return Number.isFinite(lat) && Number.isFinite(lon);
}

export function urlHasRadius(params: URLSearchParams): boolean {
  const raw = params.get("radius_km");
  return raw != null && raw !== "";
}

export function formatGpsAccuracy(meters: number | null | undefined): string | null {
  if (meters == null || !Number.isFinite(meters) || meters < 0) {
    return null;
  }
  return `±${Math.round(meters)} m`;
}

function isValidCoord(lat: number, lon: number): boolean {
  return Number.isFinite(lat) && Number.isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
}

export function parseStoredMapView(raw: string | null): StoredMapView | null {
  if (!raw) {
    return null;
  }
  try {
    const data: unknown = JSON.parse(raw);
    if (typeof data !== "object" || data == null) {
      return null;
    }
    const row = data as Record<string, unknown>;
    const latitude = Number(row.latitude);
    const longitude = Number(row.longitude);
    if (!isValidCoord(latitude, longitude)) {
      return null;
    }
    const label = typeof row.label === "string" && row.label.trim() ? row.label.trim() : `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
    const source = ORIGIN_SOURCES.includes(row.source as GeoOrigin["source"])
      ? (row.source as GeoOrigin["source"])
      : "coords";
    return {
      latitude,
      longitude,
      label,
      source,
      radiusKm: clampRadiusKm(row.radiusKm as number | string | null | undefined),
    };
  } catch {
    return null;
  }
}

export function loadStoredMapView(): StoredMapView | null {
  try {
    return parseStoredMapView(localStorage.getItem(MAP_LAST_ORIGIN_KEY));
  } catch {
    return null;
  }
}

export function saveStoredMapView(view: StoredMapView): void {
  if (!isValidCoord(view.latitude, view.longitude)) {
    return;
  }
  const payload: StoredMapView = {
    latitude: view.latitude,
    longitude: view.longitude,
    label: view.label.trim() || `${view.latitude.toFixed(5)}, ${view.longitude.toFixed(5)}`,
    source: view.source ?? "coords",
    radiusKm: clampRadiusKm(view.radiusKm ?? DEFAULT_RADIUS_KM),
  };
  try {
    localStorage.setItem(MAP_LAST_ORIGIN_KEY, JSON.stringify(payload));
  } catch {
    // private mode / quota
  }
}
