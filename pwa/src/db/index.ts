import Dexie, { type Table } from "dexie";
import type { CatalogPlace, MetaRecord, PlaceNameSnapshot, StoredPlaceState, StoredVisit } from "../catalog/types";
import type { DiaryBackup, StoredTrip } from "../diary/types";

export class PamatkyDB extends Dexie {
  places!: Table<CatalogPlace, string>;
  visits!: Table<StoredVisit, string>;
  place_states!: Table<StoredPlaceState, string>;
  meta!: Table<MetaRecord, string>;
  diary_backups!: Table<DiaryBackup, number>;
  place_snapshots!: Table<PlaceNameSnapshot, string>;
  trips!: Table<StoredTrip, string>;

  constructor() {
    super("pamatkyDenik");
    this.version(1).stores({
      places: "id, name",
      visits: "id, place_id",
      place_states: "place_id",
      meta: "key",
    });
    this.version(2).stores({
      places: "id, name",
      visits: "id, place_id",
      place_states: "place_id",
      meta: "key",
      diary_backups: "++id, created_at",
    });
    this.version(3).stores({
      places: "id, name",
      visits: "id, place_id",
      place_states: "place_id",
      meta: "key",
      diary_backups: "++id, created_at",
      place_snapshots: "place_id",
    });
    this.version(4).stores({
      places: "id, name",
      visits: "id, place_id",
      place_states: "place_id",
      meta: "key",
      diary_backups: "++id, created_at",
      place_snapshots: "place_id",
      trips: "id",
    });
  }
}

export const db = new PamatkyDB();
