export type PlaceTypeCode =
  | "CASTLE"
  | "CHATEAU"
  | "RUIN"
  | "FORTRESS"
  | "MANOR"
  | "PALACE"
  | "LOOKOUT_TOWER"
  | "ZOO"
  | "CAVE"
  | "OTHER";

export type ConditionCode = "PRESERVED" | "RUIN" | "REMAINS" | "REBUILT" | "EXTINCT" | "UNKNOWN";

export type VisitabilityCode =
  | "REGULAR"
  | "SEASONAL"
  | "BY_APPOINTMENT"
  | "EVENTS_ONLY"
  | "FREE_ACCESS"
  | "EXTERIOR_ONLY"
  | "PRIVATE"
  | "TEMPORARILY_CLOSED"
  | "CLOSED"
  | "EXTINCT"
  | "UNKNOWN";

export type HeritageStatusCode = "NONE" | "KP" | "NKP" | "UNKNOWN";

export interface CatalogAttribution {
  wikidata: string;
  npu_opendata: string;
  osm: string;
  commons: string;
}

export interface CatalogLocation {
  latitude: number | null;
  longitude: number | null;
  address: string | null;
  municipality: string | null;
  district: string | null;
  region: string | null;
  country: string;
}

export interface CatalogLinks {
  official: string | null;
  wikipedia: string | null;
  wikidata: string | null;
  heritage_catalog: string | null;
  opening_hours: string | null;
  tickets: string | null;
}

export interface CatalogImage {
  thumbnail_url: string | null;
  original_url: string | null;
  attribution: string | null;
  license: string | null;
  license_url: string | null;
}

export interface CatalogPlace {
  id: string;
  name: string;
  short_name: string | null;
  alternative_names: string[];
  types: PlaceTypeCode[];
  condition: ConditionCode;
  visitability: VisitabilityCode;
  short_description: string | null;
  heritage_status: HeritageStatusCode | null;
  unesco: boolean;
  location: CatalogLocation;
  links: CatalogLinks;
  image: CatalogImage | null;
  /** OSM opening_hours syntax. Chybí u starších catalog.json (schema 1 bez pole). */
  osm_opening_hours?: string | null;
  phone?: string | null;
  fee?: string | null;
  wheelchair?: string | null;
  parking?: string | null;
  visit_duration_minutes?: number | null;
  last_entry?: string | null;
  dogs?: string | null;
  payment?: string | null;
  amenities?: Array<"toilets" | "cafe" | "playground">;
  inception_year?: number | null;
  architectural_style?: string | null;
}

export interface Catalog {
  schema_version: number;
  catalog_version: number;
  generated_at: string;
  attribution: CatalogAttribution;
  places: CatalogPlace[];
}

export interface CatalogDiff {
  added: number;
  changed: number;
  removed: number;
  unchanged: number;
  addedIds: string[];
  changedIds: string[];
  removedIds: string[];
}

export interface StoredVisit {
  id: string;
  place_id: string;
  visited_at: string | null;
  rating: number | null;
  people: string[];
  note: string | null;
  trip_id?: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface StoredPlaceState {
  place_id: string;
  want_to_visit: boolean;
  favorite: boolean;
  personal_note: string | null;
  updated_at: string;
  deleted_at: string | null;
}

export interface MetaRecord {
  key: string;
  value: unknown;
}

export interface PlaceNameSnapshot {
  place_id: string;
  name: string;
  municipality: string | null;
  updated_at: string;
}

export const SUPPORTED_SCHEMA_VERSION = 1;
