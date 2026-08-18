import { capNearbyHits, type NearbyHit } from "./nearby";
import type { CatalogPlace } from "../catalog/types";
import { hasGps } from "../catalog/labels";
import { haversineKm } from "./haversine";
import { closestPointOnSegment, type LatLon } from "./corridor";

export const GPX_CORRIDOR_KM = 0.4;
export const GPX_MAX_POINTS = 320;

function pushTrackPoint(points: LatLon[], point: LatLon): void {
  points.push(point);
  if (points.length >= GPX_MAX_POINTS * 2) {
    const next = downsampleTrack(points, GPX_MAX_POINTS);
    points.length = 0;
    points.push(...next);
  }
}

function pointsFromDom(xml: string): LatLon[] | null {
  if (typeof DOMParser === "undefined") {
    return null;
  }
  const doc = new DOMParser().parseFromString(xml, "application/xml");
  if (doc.querySelector("parsererror")) {
    throw new Error("Soubor GPX se nepodařilo přečíst.");
  }
  const points: LatLon[] = [];
  const collections = [doc.getElementsByTagName("trkpt"), doc.getElementsByTagName("rtept"), doc.getElementsByTagName("wpt")];
  for (const nodes of collections) {
    for (let i = 0; i < nodes.length; i += 1) {
      const node = nodes.item(i);
      if (!node) {
        continue;
      }
      const lat = Number(node.getAttribute("lat"));
      const lon = Number(node.getAttribute("lon"));
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        continue;
      }
      pushTrackPoint(points, { latitude: lat, longitude: lon });
    }
  }
  return points;
}

function pointsFromRegex(xml: string): LatLon[] {
  const points: LatLon[] = [];
  const tags = xml.matchAll(/<(?:trkpt|rtept|wpt)\b[^>]*>/gi);
  for (const match of tags) {
    const tag = match[0];
    const lat = Number(/\blat="([^"]+)"/i.exec(tag)?.[1]);
    const lon = Number(/\blon="([^"]+)"/i.exec(tag)?.[1]);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      continue;
    }
    pushTrackPoint(points, { latitude: lat, longitude: lon });
  }
  return points;
}

export function parseGpxTrack(xml: string): LatLon[] {
  const points = pointsFromDom(xml) ?? pointsFromRegex(xml);
  if (points.length === 0) {
    const nameMatch = /<name>([^<]+)<\/name>/i.exec(xml);
    const name = nameMatch?.[1]?.trim();
    if (name) {
      throw new Error(`GPX „${name}“ nemá souřadnice.`);
    }
    throw new Error("V GPX nejsou žádné body trasy.");
  }
  return downsampleTrack(points, GPX_MAX_POINTS);
}

export function downsampleTrack(points: LatLon[], maxPoints: number): LatLon[] {
  if (points.length <= maxPoints) {
    return points;
  }
  const step = Math.ceil(points.length / maxPoints);
  const out: LatLon[] = [];
  for (let i = 0; i < points.length; i += step) {
    const point = points[i];
    if (point) {
      out.push(point);
    }
  }
  const last = points[points.length - 1];
  if (last && out[out.length - 1] !== last) {
    out.push(last);
  }
  return out;
}

function distanceToTrackKm(point: LatLon, track: LatLon[]): number | null {
  if (track.length === 0) {
    return null;
  }
  if (track.length === 1) {
    const only = track[0];
    if (!only) {
      return null;
    }
    return haversineKm(point.latitude, point.longitude, only.latitude, only.longitude);
  }
  let best: number | null = null;
  for (let i = 1; i < track.length; i += 1) {
    const a = track[i - 1];
    const b = track[i];
    if (!a || !b) {
      continue;
    }
    const closest = closestPointOnSegment(point, a, b);
    const km = haversineKm(point.latitude, point.longitude, closest.latitude, closest.longitude);
    if (km != null && (best == null || km < best)) {
      best = km;
    }
  }
  return best;
}

export function placesAlongTrack(
  places: CatalogPlace[],
  track: LatLon[],
  corridorKm = GPX_CORRIDOR_KM,
): NearbyHit[] {
  const buffer = corridorKm > 0 ? corridorKm : GPX_CORRIDOR_KM;
  const hits: NearbyHit[] = [];
  for (const place of places) {
    if (!hasGps(place) || place.location.latitude == null || place.location.longitude == null) {
      continue;
    }
    const km = distanceToTrackKm(
      { latitude: place.location.latitude, longitude: place.location.longitude },
      track,
    );
    if (km == null || km > buffer) {
      continue;
    }
    hits.push({ place, km });
  }
  hits.sort((a, b) => a.km - b.km || a.place.name.localeCompare(b.place.name, "cs"));
  return capNearbyHits(hits).hits;
}
