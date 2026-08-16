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
