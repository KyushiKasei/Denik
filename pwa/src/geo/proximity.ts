import type { CatalogPlace } from "../catalog/types";
import { hasGps } from "../catalog/labels";
import { haversineKm } from "./haversine";
import type { NearbyHit } from "./nearby";

/** iOS PWA nemá geofence na pozadí — práh při otevření Dnes/Mapy. */
export const PROXIMITY_KM = 0.3;
const DISMISS_KEY = "pamatky.proximity.dismissed";

export function nearestPlaceHere(
  places: CatalogPlace[],
  here: { latitude: number; longitude: number },
  maxKm = PROXIMITY_KM,
): NearbyHit | null {
  let best: NearbyHit | null = null;
  for (const place of places) {
    if (!hasGps(place) || place.location.latitude == null || place.location.longitude == null) {
      continue;
    }
    const km = haversineKm(here.latitude, here.longitude, place.location.latitude, place.location.longitude);
    if (km == null || km > maxKm) {
      continue;
    }
    if (!best || km < best.km) {
      best = { place, km };
    }
  }
  return best;
}

export function loadDismissedProximityId(): string | null {
  try {
    return sessionStorage.getItem(DISMISS_KEY);
  } catch {
    return null;
  }
}

export function dismissProximity(placeId: string): void {
  try {
    sessionStorage.setItem(DISMISS_KEY, placeId);
  } catch {
    // private mode
  }
}
