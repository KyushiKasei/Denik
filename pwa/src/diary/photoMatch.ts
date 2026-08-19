import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { hasGps } from "../catalog/labels";
import { haversineKm } from "../geo/haversine";
import type { PhotoExif } from "./exif";
import { addVisitPhoto } from "./photos";
import { stampVisitToday } from "./stamp";
import { todayIsoDate } from "./ids";
import { loadVisitsForPlace } from "./store";

/** Předvybrat místo, když je fotka opravdu u něj. */
export const PHOTO_MATCH_MAX_KM = 0.5;
/** Nabídnout nejbližší místo i z větší dálky (nádvoří vs. GPS věže). */
export const PHOTO_SUGGEST_MAX_KM = 2;
export const PHOTO_NEARBY_MAX_KM = 5;
export const PHOTO_NEARBY_LIMIT = 5;

export interface PhotoPlaceHit {
  place: CatalogPlace;
  km: number;
}

export interface PhotoPlaceMatch {
  file: File;
  exif: PhotoExif;
  place: CatalogPlace | null;
  km: number | null;
  nearby: PhotoPlaceHit[];
  confident: boolean;
  visitedAt: string;
}

export function nearestPlacesByExif(
  places: CatalogPlace[],
  exif: PhotoExif,
  maxKm = PHOTO_NEARBY_MAX_KM,
  limit = PHOTO_NEARBY_LIMIT,
): PhotoPlaceHit[] {
  if (exif.latitude == null || exif.longitude == null) {
    return [];
  }
  const hits: PhotoPlaceHit[] = [];
  for (const place of places) {
    if (!hasGps(place) || place.location.latitude == null || place.location.longitude == null) {
      continue;
    }
    const km = haversineKm(exif.latitude, exif.longitude, place.location.latitude, place.location.longitude);
    if (km == null || km > maxKm) {
      continue;
    }
    hits.push({ place, km });
  }
  hits.sort((a, b) => a.km - b.km);
  return hits.slice(0, limit);
}

export function matchExifToPlace(
  places: CatalogPlace[],
  exif: PhotoExif,
  maxKm = PHOTO_MATCH_MAX_KM,
): PhotoPlaceHit | null {
  return nearestPlacesByExif(places, exif, maxKm, 1)[0] ?? null;
}

export function suggestPhotoMatches(files: File[], places: CatalogPlace[], exifs: PhotoExif[]): PhotoPlaceMatch[] {
  return files.map((file, index) => {
    const exif = exifs[index] ?? { latitude: null, longitude: null, takenAt: null };
    const nearby = nearestPlacesByExif(places, exif);
    const suggested = nearby.find((hit) => hit.km <= PHOTO_SUGGEST_MAX_KM) ?? null;
    const confident = suggested != null && suggested.km <= PHOTO_MATCH_MAX_KM;
    return {
      file,
      exif,
      place: suggested?.place ?? null,
      km: suggested?.km ?? null,
      nearby,
      confident,
      visitedAt: exif.takenAt || todayIsoDate(),
    };
  });
}

export type PhotoVisitChoice = { kind: "existing"; visitId: string } | { kind: "create"; visitedAt: string };

function visitDay(visit: StoredVisit): string {
  return (visit.visited_at || "").trim();
}

export function liveVisitsForPlace(visits: StoredVisit[], placeId: string): StoredVisit[] {
  return visits
    .filter((visit) => !visit.deleted_at && visit.place_id === placeId)
    .sort((a, b) => visitDay(b).localeCompare(visitDay(a)) || b.created_at.localeCompare(a.created_at));
}

/** Stejný den z EXIF, jinak dnešní návštěva místa, jinak poslední, jinak nová s datem z fotky. */
export function defaultPhotoVisitChoice(
  visits: StoredVisit[],
  placeId: string,
  exifDay: string,
  today: string,
): PhotoVisitChoice {
  const forPlace = liveVisitsForPlace(visits, placeId);
  const day = exifDay.trim() || today;
  const sameDay = forPlace.find((visit) => visitDay(visit) === day);
  if (sameDay) {
    return { kind: "existing", visitId: sameDay.id };
  }
  const todayVisit = forPlace.find((visit) => visitDay(visit) === today);
  if (todayVisit) {
    return { kind: "existing", visitId: todayVisit.id };
  }
  if (forPlace[0]) {
    return { kind: "existing", visitId: forPlace[0].id };
  }
  return { kind: "create", visitedAt: day };
}

export async function applyPhotoMatch(match: PhotoPlaceMatch, choice: PhotoVisitChoice): Promise<void> {
  if (!match.place) {
    throw new Error("Fotce chybí místo.");
  }
  if (choice.kind === "existing") {
    const visits = await loadVisitsForPlace(match.place.id);
    const visit = visits.find((row) => row.id === choice.visitId);
    if (!visit) {
      throw new Error("Vybraná návštěva už není v deníku.");
    }
    await addVisitPhoto(visit.id, match.file);
    return;
  }
  const visitedAt = choice.visitedAt.trim() || match.visitedAt || todayIsoDate();
  const { visit } = await stampVisitToday(match.place.id, null, visitedAt);
  await addVisitPhoto(visit.id, match.file);
}
