import type { StoredPlaceState, StoredVisit } from "../catalog/types";

export const DIARY_SCHEMA_VERSION = 2;
export const SUPPORTED_DIARY_SCHEMA_VERSIONS = [1, 2] as const;

export type DiaryExportedFrom = "pwa" | "pc";

export interface TripOrigin {
  latitude: number;
  longitude: number;
  label: string;
}

export interface StoredTripStop {
  place_id: string;
  sort_order: number;
  note: string | null;
}

export type TripStatus = "planned" | "partial" | "done";

export interface StoredTrip {
  id: string;
  name: string;
  planned_on: string | null;
  origin: TripOrigin | null;
  notes: string | null;
  status?: TripStatus;
  stops: StoredTripStop[];
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface Diary {
  schema_version: number;
  exported_at: string;
  exported_from: DiaryExportedFrom;
  place_states: StoredPlaceState[];
  visits: StoredVisit[];
  trips: StoredTrip[];
}

export interface DiaryMergeCounts {
  visitsInserted: number;
  visitsUpdated: number;
  visitsUnchanged: number;
  statesInserted: number;
  statesUpdated: number;
  statesUnchanged: number;
  tripsInserted: number;
  tripsUpdated: number;
  tripsUnchanged: number;
  familyCollapsed?: number;
  warnings: string[];
}

export interface DiaryBackup {
  id?: number;
  created_at: string;
  diary: Diary;
}

export interface DiaryMeta {
  last_export_at: string | null;
  last_import_at: string | null;
  visits_at_last_export: number;
}

export interface StoredVisitPhoto {
  id: string;
  visit_id: string;
  mime: string;
  blob: Blob;
  created_at: string;
}

