/** Stejný vzorec jako pc-app/app/services/geo.py. */

export const EARTH_RADIUS_M = 6_371_000;
export const DEFAULT_RADIUS_KM = 30;
export const MIN_RADIUS_KM = 5;
export const MAX_RADIUS_KM = 150;
export const RADIUS_STEP_KM = 5;

export function haversineKm(
  lat1: number | null | undefined,
  lon1: number | null | undefined,
  lat2: number | null | undefined,
  lon2: number | null | undefined,
): number | null {
  if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) {
    return null;
  }
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const dphi = toRad(lat2 - lat1);
  const dlmb = toRad(lon2 - lon1);
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlmb / 2) ** 2;
  return (2 * EARTH_RADIUS_M * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))) / 1000;
}

export function clampRadiusKm(raw: number | string | null | undefined): number {
  if (raw == null || raw === "") {
    return DEFAULT_RADIUS_KM;
  }
  const value = Math.round(Number(String(raw).replace(",", ".")));
  if (!Number.isFinite(value)) {
    return DEFAULT_RADIUS_KM;
  }
  return Math.max(MIN_RADIUS_KM, Math.min(MAX_RADIUS_KM, value));
}
