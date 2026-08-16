import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import diarySchema from "@shared/schemas/diary.schema.json";
import { DiaryImportError } from "./errors";
import { SUPPORTED_DIARY_SCHEMA_VERSIONS, type Diary } from "./types";

const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
const validateFn = ajv.compile(diarySchema);

function formatAjvErrors(): string {
  const errors = validateFn.errors ?? [];
  const parts = errors.slice(0, 8).map((err) => {
    const path = err.instancePath ? err.instancePath.replace(/^\//, "").replaceAll("/", ".") : "(kořen)";
    return `${path}: ${err.message ?? "neplatná hodnota"}`;
  });
  return parts.join(" | ");
}

export function parseDiaryJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err);
    throw new DiaryImportError(`Soubor není platný JSON: ${detail}`);
  }
}

export function validateDiary(data: unknown): Diary {
  if (data === null || typeof data !== "object" || Array.isArray(data)) {
    throw new DiaryImportError("Deník musí být JSON objekt.");
  }
  const record = data as Record<string, unknown>;
  const schemaVersion = record.schema_version;
  if (schemaVersion !== 1 && schemaVersion !== 2) {
    throw new DiaryImportError(
      `Neznámá nebo nepodporovaná schema_version ${JSON.stringify(schemaVersion)}. Přijímá se ${SUPPORTED_DIARY_SCHEMA_VERSIONS.join(" a ")}.`,
    );
  }
  if (schemaVersion === 2 && !("trips" in record)) {
    throw new DiaryImportError("Nevalidní diary.json. Verze 2 musí obsahovat pole trips.");
  }
  if (!validateFn(data)) {
    throw new DiaryImportError(`Nevalidní diary.json. ${formatAjvErrors()}`);
  }
  if (!Array.isArray(record.trips)) {
    record.trips = [];
  }
  const diary = data as unknown as Diary;
  const visitIds = diary.visits.map((visit) => visit.id);
  if (new Set(visitIds).size !== visitIds.length) {
    throw new DiaryImportError("Nevalidní diary.json. Duplicitní visits[].id.");
  }
  const placeIds = diary.place_states.map((state) => state.place_id);
  if (new Set(placeIds).size !== placeIds.length) {
    throw new DiaryImportError("Nevalidní diary.json. Duplicitní place_states[].place_id.");
  }
  const tripIds = diary.trips.map((trip) => trip.id);
  if (new Set(tripIds).size !== tripIds.length) {
    throw new DiaryImportError("Nevalidní diary.json. Duplicitní trips[].id.");
  }
  return diary;
}

export function loadDiaryFromText(text: string): Diary {
  return validateDiary(parseDiaryJson(text));
}
