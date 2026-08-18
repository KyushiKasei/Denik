import type { CatalogPlace } from "../catalog/types";
import { hasGps } from "../catalog/labels";
import { haversineKm } from "../geo/haversine";
import type { PhotoExif } from "./exif";
import { addVisitPhoto } from "./photos";
import { stampVisitToday } from "./stamp";
import { todayIsoDate } from "./ids";

export const PHOTO_MATCH_MAX_KM = 0.5;

export interface PhotoPlaceMatch {
  file: File;
  exif: PhotoExif;
  place: CatalogPlace | null;
  km: number | null;
  visitedAt: string;
}

export function matchExifToPlace(
  places: CatalogPlace[],
  exif: PhotoExif,
  maxKm = PHOTO_MATCH_MAX_KM,
): { place: CatalogPlace; km: number } | null {
  if (exif.latitude == null || exif.longitude == null) {
    return null;
  }
  let best: { place: CatalogPlace; km: number } | null = null;
  for (const place of places) {
    if (!hasGps(place) || place.location.latitude == null || place.location.longitude == null) {
      continue;
    }
    const km = haversineKm(exif.latitude, exif.longitude, place.location.latitude, place.location.longitude);
    if (km == null || km > maxKm) {
      continue;
    }
    if (!best || km < best.km) {
      best = { place, km };
    }
  }
  return best;
}

export function suggestPhotoMatches(files: File[], places: CatalogPlace[], exifs: PhotoExif[]): PhotoPlaceMatch[] {
  return files.map((file, index) => {
    const exif = exifs[index] ?? { latitude: null, longitude: null, takenAt: null };
    const hit = matchExifToPlace(places, exif);
    return {
      file,
      exif,
      place: hit?.place ?? null,
      km: hit?.km ?? null,
      visitedAt: exif.takenAt || todayIsoDate(),
    };
  });
}

export async function applyPhotoMatch(match: PhotoPlaceMatch): Promise<void> {
  if (!match.place) {
    throw new Error("Fotce chybí místo.");
  }
  const { visit } = await stampVisitToday(match.place.id, null, match.visitedAt);
  await addVisitPhoto(visit.id, match.file);
}
