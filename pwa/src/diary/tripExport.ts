import type { CatalogPlace } from "../catalog/types";
import { formatOpeningHours } from "../catalog/openingHours";
import { hasGps } from "../catalog/labels";
import type { StoredTrip } from "./types";
import { orderedStops } from "./tripPlan";

export interface LatLon {
  latitude: number;
  longitude: number;
}

function icsEscape(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
}

function icsDate(iso: string): string {
  return iso.replace(/-/g, "");
}

function nextIsoDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) {
    return iso;
  }
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + 1);
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function tripStopPlaces(trip: StoredTrip, placesById: Map<string, CatalogPlace>): CatalogPlace[] {
  return orderedStops(trip)
    .map((stop) => placesById.get(stop.place_id))
    .filter((place): place is CatalogPlace => Boolean(place));
}

export function buildTripIcs(trip: StoredTrip, placesById: Map<string, CatalogPlace>): string {
  const names = tripStopPlaces(trip, placesById).map((place) => place.name);
  const day = trip.planned_on || new Date().toISOString().slice(0, 10);
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const description = names.length ? names.join(", ") : "Zatím bez zastávek.";
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//PamatkyDenik//CS",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:${trip.id}@pamatky-denik`,
    `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${icsDate(day)}`,
    `DTEND;VALUE=DATE:${icsDate(nextIsoDate(day))}`,
    `SUMMARY:${icsEscape(trip.name)}`,
    `DESCRIPTION:${icsEscape(description)}`,
    "END:VEVENT",
    "END:VCALENDAR",
    "",
  ];
  return lines.join("\r\n");
}

export function buildTripGpx(trip: StoredTrip, placesById: Map<string, CatalogPlace>): string {
  const waypoints = tripStopPlaces(trip, placesById).filter(hasGps);
  const body = waypoints
    .map((place) => {
      const name = place.name.replace(/&/g, "&amp;").replace(/</g, "&lt;");
      return `  <wpt lat="${place.location.latitude}" lon="${place.location.longitude}">\n    <name>${name}</name>\n  </wpt>`;
    })
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="PamatkyDenik">\n${body}\n</gpx>\n`;
}

export function googleMapsMultiStopUrl(
  origin: LatLon | null,
  places: CatalogPlace[],
): string | null {
  const coords = places
    .filter(hasGps)
    .map((place) => `${place.location.latitude},${place.location.longitude}`);
  if (coords.length === 0) {
    return null;
  }
  const params = new URLSearchParams({ api: "1" });
  if (origin) {
    params.set("origin", `${origin.latitude},${origin.longitude}`);
  } else {
    params.set("origin", coords[0] ?? "");
  }
  params.set("destination", coords[coords.length - 1] ?? "");
  if (coords.length > 2) {
    params.set("waypoints", coords.slice(origin ? 0 : 1, -1).join("|"));
  } else if (coords.length === 2 && origin) {
    params.set("waypoints", coords[0] ?? "");
  }
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

export function mapyCzMultiStopUrl(origin: LatLon | null, places: CatalogPlace[]): string | null {
  const points: LatLon[] = [];
  if (origin) {
    points.push(origin);
  }
  for (const place of places) {
    if (hasGps(place) && place.location.latitude != null && place.location.longitude != null) {
      points.push({ latitude: place.location.latitude, longitude: place.location.longitude });
    }
  }
  if (points.length < 1) {
    return null;
  }
  const start = points[0];
  const end = points[points.length - 1];
  if (!start || !end) {
    return null;
  }
  return `https://mapy.cz/fnc/v1/route?start=${start.longitude},${start.latitude}&end=${end.longitude},${end.latitude}`;
}

export function downloadTextFile(filename: string, mime: string, text: string): void {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function tripSheetLines(trip: StoredTrip, placesById: Map<string, CatalogPlace>): string[] {
  const lines: string[] = [`${trip.name}${trip.planned_on ? ` · ${trip.planned_on}` : ""}`];
  orderedStops(trip).forEach((stop, index) => {
    const place = placesById.get(stop.place_id);
    const hours = place ? formatOpeningHours(place.osm_opening_hours) : null;
    const gps =
      place && hasGps(place) ? `${place.location.latitude}, ${place.location.longitude}` : "bez GPS";
    lines.push(`${index + 1}. ${place?.name ?? "Místo"} · ${gps}${hours ? ` · ${hours}` : ""}`);
  });
  return lines;
}
