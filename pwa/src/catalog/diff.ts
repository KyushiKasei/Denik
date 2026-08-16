import type { CatalogDiff, CatalogPlace } from "./types";

function placeKey(place: CatalogPlace): string {
  return JSON.stringify(place);
}

export function diffPlaces(current: CatalogPlace[], incoming: CatalogPlace[]): CatalogDiff {
  const currentById = new Map(current.map((place) => [place.id, place]));
  const incomingIds = new Set(incoming.map((place) => place.id));
  const addedIds: string[] = [];
  const changedIds: string[] = [];
  let unchanged = 0;

  for (const place of incoming) {
    const existing = currentById.get(place.id);
    if (!existing) {
      addedIds.push(place.id);
    } else if (placeKey(existing) === placeKey(place)) {
      unchanged += 1;
    } else {
      changedIds.push(place.id);
    }
  }

  const removedIds = current.filter((place) => !incomingIds.has(place.id)).map((place) => place.id);

  return {
    added: addedIds.length,
    changed: changedIds.length,
    removed: removedIds.length,
    unchanged,
    addedIds,
    changedIds,
    removedIds,
  };
}
