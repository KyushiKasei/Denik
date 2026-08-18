import { db } from "../db";
import { persistStorage } from "../storage/persist";
import { diffPlaces } from "./diff";
import type { Catalog, CatalogDiff, CatalogPlace } from "./types";

export interface CatalogMeta {
  catalog_version: number | null;
  schema_version: number | null;
  generated_at: string | null;
  imported_at: string | null;
  attribution: Catalog["attribution"] | null;
}

async function metaValue<T>(key: string): Promise<T | undefined> {
  const row = await db.meta.get(key);
  return row?.value as T | undefined;
}

let placesCache: CatalogPlace[] | null = null;

export function peekPlaces(): CatalogPlace[] | null {
  return placesCache;
}

export function invalidatePlacesCache(): void {
  placesCache = null;
}

export async function loadPlaces(): Promise<CatalogPlace[]> {
  if (placesCache) {
    return placesCache;
  }
  const rows = await db.places.toArray();
  // Import mezitím mohl naplnit cache — starý toArray ji nesmí přepsat.
  if (placesCache) {
    return placesCache;
  }
  placesCache = rows;
  return placesCache;
}

export async function getPlace(id: string): Promise<CatalogPlace | undefined> {
  if (placesCache) {
    return placesCache.find((place) => place.id === id);
  }
  return db.places.get(id);
}

export async function getPlaceSnapshot(placeId: string) {
  return db.place_snapshots.get(placeId);
}

export async function loadPlaceSnapshots() {
  return db.place_snapshots.toArray();
}

export async function loadCatalogMeta(): Promise<CatalogMeta> {
  const [catalog_version, schema_version, generated_at, imported_at, attribution] = await Promise.all([
    metaValue<number>("catalog_version"),
    metaValue<number>("schema_version"),
    metaValue<string>("generated_at"),
    metaValue<string>("imported_at"),
    metaValue<Catalog["attribution"]>("attribution"),
  ]);
  return {
    catalog_version: catalog_version ?? null,
    schema_version: schema_version ?? null,
    generated_at: generated_at ?? null,
    imported_at: imported_at ?? null,
    attribution: attribution ?? null,
  };
}

export async function previewCatalogImport(catalog: Catalog): Promise<CatalogDiff> {
  const current = await loadPlaces();
  return diffPlaces(current, catalog.places);
}

export function catalogVersionAlreadyLoaded(currentVersion: number | null, incomingVersion: number): boolean {
  return currentVersion != null && currentVersion === incomingVersion;
}

export async function replacePlacesStore(catalog: Catalog): Promise<CatalogDiff> {
  const current = await loadPlaces();
  const diff = diffPlaces(current, catalog.places);
  const importedAt = new Date().toISOString();

  await db.transaction("rw", db.places, db.meta, db.place_snapshots, async () => {
    if (current.length > 0) {
      await db.place_snapshots.bulkPut(
        current.map((place) => ({
          place_id: place.id,
          name: place.name,
          municipality: place.location.municipality,
          updated_at: importedAt,
        })),
      );
    }
    await db.places.clear();
    if (catalog.places.length > 0) {
      await db.places.bulkPut(catalog.places);
    }
    await db.meta.put({ key: "catalog_version", value: catalog.catalog_version });
    await db.meta.put({ key: "schema_version", value: catalog.schema_version });
    await db.meta.put({ key: "generated_at", value: catalog.generated_at });
    await db.meta.put({ key: "attribution", value: catalog.attribution });
    await db.meta.put({ key: "imported_at", value: importedAt });
  });
  // Až po commitu — jinak rollback Dexie nechá UI u nového katalogu.
  placesCache = catalog.places;

  await persistStorage();
  return diff;
}
