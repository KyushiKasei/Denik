import type { CatalogPlace } from "../catalog/types";
import type { DiaryFilterSets, PlaceFilters } from "../catalog/filterPlaces";
import { filterPlaces } from "../catalog/filterPlaces";
import { hasGps } from "../catalog/labels";
import { clampRadiusKm, haversineKm } from "./haversine";

export interface NearbyHit {
  place: CatalogPlace;
  km: number;
}

export function placesNearby(
  places: CatalogPlace[],
  origin: { latitude: number; longitude: number },
  radiusKm: number,
  filters: PlaceFilters,
  diary?: DiaryFilterSets,
): { hits: NearbyHit[]; skippedNoGps: number } {
  const skippedNoGps = places.filter((place) => !hasGps(place)).length;
  const radius = clampRadiusKm(radiusKm);
  const withGps = places.filter(hasGps);
  const filtered = filterPlaces(withGps, { ...filters, query: "" }, diary);
  const hits: NearbyHit[] = [];
  for (const place of filtered) {
    const km = haversineKm(origin.latitude, origin.longitude, place.location.latitude, place.location.longitude);
    if (km == null || km > radius) {
      continue;
    }
    hits.push({ place, km });
  }
  hits.sort((a, b) => a.km - b.km || a.place.name.localeCompare(b.place.name, "cs"));
  return { hits, skippedNoGps };
}
