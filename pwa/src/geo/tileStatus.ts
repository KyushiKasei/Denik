/** Stejná URL jako PC nearby.js — OSM už a/b/c subdomény nedoručuje. */
export const OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
export const OSM_TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

export type MapTileStatus = "online" | "offline-cached" | "offline-miss";

export function mapTileStatus(online: boolean, tileError: boolean): MapTileStatus {
  if (online) {
    return "online";
  }
  return tileError ? "offline-miss" : "offline-cached";
}

export function mapTileStatusLabel(status: MapTileStatus): string {
  if (status === "online") {
    return "Mapa: online";
  }
  if (status === "offline-cached") {
    return "Mapa: poslední stažené dlaždice (offline)";
  }
  return "Mapa: dlaždice nejsou v mezipaměti";
}
