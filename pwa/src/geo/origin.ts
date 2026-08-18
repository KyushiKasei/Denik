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

/** Krajská města — střed obce, ne první hrad v katalogu. */
const KNOWN_SETTLEMENTS: Record<string, { latitude: number; longitude: number; label: string }> = {
  praha: { latitude: 50.0875, longitude: 14.4213, label: "Praha" },
  "hlavni mesto praha": { latitude: 50.0875, longitude: 14.4213, label: "Praha" },
  brno: { latitude: 49.1951, longitude: 16.6068, label: "Brno" },
  ostrava: { latitude: 49.8346, longitude: 18.282, label: "Ostrava" },
  plzen: { latitude: 49.7475, longitude: 13.3776, label: "Plzeň" },
  liberec: { latitude: 50.7671, longitude: 15.0562, label: "Liberec" },
  olomouc: { latitude: 49.5938, longitude: 17.2509, label: "Olomouc" },
  "ceske budejovice": { latitude: 48.9745, longitude: 14.4743, label: "České Budějovice" },
  "hradec kralove": { latitude: 50.2093, longitude: 15.8328, label: "Hradec Králové" },
  "usti nad labem": { latitude: 50.6607, longitude: 14.0323, label: "Ústí nad Labem" },
  pardubice: { latitude: 50.0343, longitude: 15.7812, label: "Pardubice" },
  zlin: { latitude: 49.2265, longitude: 17.6707, label: "Zlín" },
  jihlava: { latitude: 49.3961, longitude: 15.5912, label: "Jihlava" },
  "karlovy vary": { latitude: 50.2315, longitude: 12.872, label: "Karlovy Vary" },
};

export function knownSettlement(q: string): GeoOrigin | null {
  const hit = KNOWN_SETTLEMENTS[fold(q.trim())];
  if (!hit) {
    return null;
  }
  return { ...hit, source: "municipality" };
}

function centroidOf(rows: Array<{ location: { latitude: number; longitude: number } }>, label: string): GeoOrigin {
  const latitude = rows.reduce((sum, row) => sum + row.location.latitude, 0) / rows.length;
  const longitude = rows.reduce((sum, row) => sum + row.location.longitude, 0) / rows.length;
  return { latitude, longitude, label, source: "municipality" };
}

export function suggestOrigins(places: CatalogPlace[], q: string, limit = 8): GeoOrigin[] {
  const term = fold(appliedSearchQuery(q));
  if (!term) {
    return [];
  }
  const out: GeoOrigin[] = [];
  const settlement = knownSettlement(q);
  if (settlement) {
    out.push(settlement);
  }
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
  const known = knownSettlement(q);
  if (known) {
    return known;
  }
  const withGps = places.filter(
    (place): place is CatalogPlace & { location: CatalogPlace["location"] & { latitude: number; longitude: number } } =>
      hasGps(place) && place.location.latitude != null && place.location.longitude != null,
  );

  const exactName = withGps.filter((place) => fold(place.name) === needle);
  if (exactName.length === 1 && exactName[0]) {
    const place = exactName[0];
    return { latitude: place.location.latitude, longitude: place.location.longitude, label: place.name, source: "place" };
  }

  const exactMuni = withGps.filter((place) => fold(place.location.municipality ?? "") === needle);
  if (exactMuni.length > 0) {
    const label = exactMuni[0]?.location.municipality || q.trim();
    const fromName = knownSettlement(label);
    if (fromName) {
      return fromName;
    }
    if (exactMuni.length >= 2) {
      return centroidOf(exactMuni, label);
    }
    const place = exactMuni[0];
    if (place) {
      return {
        latitude: place.location.latitude,
        longitude: place.location.longitude,
        label,
        source: "municipality",
      };
    }
  }

  if (exactName[0]) {
    const place = exactName[0];
    return { latitude: place.location.latitude, longitude: place.location.longitude, label: place.name, source: "place" };
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

type NominatimRow = {
  lat?: string;
  lon?: string;
  display_name?: string;
  addresstype?: string;
  type?: string;
  class?: string;
};

function nominatimRank(row: NominatimRow): number {
  const kind = `${row.addresstype ?? ""} ${row.type ?? ""}`.toLowerCase();
  if (/\b(city|town|municipality|administrative)\b/.test(kind)) {
    return 0;
  }
  if (row.class === "place" && /\b(city|town|village|municipality)\b/.test(row.type ?? "")) {
    return 1;
  }
  if (row.class === "boundary") {
    return 2;
  }
  return 9;
}

function originFromNominatimRow(row: NominatimRow, fallbackLabel: string): GeoOrigin | null {
  const latitude = Number(row.lat);
  const longitude = Number(row.lon);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return null;
  }
  const display = (row.display_name || "").split(",")[0]?.trim();
  return {
    latitude,
    longitude,
    label: display || fallbackLabel,
    source: "nominatim",
  };
}

export async function geocodeNominatim(q: string): Promise<GeoOrigin | null> {
  const term = q.trim();
  if (term.length < 2) {
    return null;
  }
  const known = knownSettlement(term);
  if (known) {
    return known;
  }
  const url = new URL(NOMINATIM_URL);
  url.searchParams.set("q", term);
  url.searchParams.set("format", "json");
  url.searchParams.set("limit", "5");
  url.searchParams.set("addressdetails", "1");
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
    if (!Array.isArray(data) || data.length === 0) {
      return null;
    }
    const rows = data.filter((row): row is NominatimRow => typeof row === "object" && row != null);
    rows.sort((a, b) => nominatimRank(a) - nominatimRank(b));
    for (const row of rows) {
      const origin = originFromNominatimRow(row, term);
      if (origin) {
        return origin;
      }
    }
    return null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
