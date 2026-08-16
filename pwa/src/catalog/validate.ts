import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import catalogSchema from "@shared/schemas/catalog.schema.json";
import { CatalogImportError } from "./errors";
import { SUPPORTED_SCHEMA_VERSION, type Catalog } from "./types";

const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
const validateFn = ajv.compile(catalogSchema);

function formatAjvErrors(): string {
  const errors = validateFn.errors ?? [];
  const parts = errors.slice(0, 8).map((err) => {
    const path = err.instancePath ? err.instancePath.replace(/^\//, "").replaceAll("/", ".") : "(kořen)";
    return `${path}: ${err.message ?? "neplatná hodnota"}`;
  });
  return parts.join(" | ");
}

export function parseCatalogJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err);
    throw new CatalogImportError(`Soubor není platný JSON: ${detail}`);
  }
}

export function validateCatalog(data: unknown): Catalog {
  if (data === null || typeof data !== "object" || Array.isArray(data)) {
    throw new CatalogImportError("Katalog musí být JSON objekt.");
  }
  const record = data as Record<string, unknown>;
  const schemaVersion = record.schema_version;
  if (schemaVersion !== SUPPORTED_SCHEMA_VERSION) {
    throw new CatalogImportError(
      `Neznámá nebo nepodporovaná schema_version ${JSON.stringify(schemaVersion)}. MVP přijímá jen ${SUPPORTED_SCHEMA_VERSION}.`,
    );
  }
  if (!validateFn(data)) {
    throw new CatalogImportError(`Nevalidní catalog.json. ${formatAjvErrors()}`);
  }
  const catalog = data as unknown as Catalog;
  const ids = catalog.places.map((place) => place.id);
  if (new Set(ids).size !== ids.length) {
    throw new CatalogImportError("Nevalidní catalog.json. Duplicitní places[].id.");
  }
  return catalog;
}

export function loadCatalogFromText(text: string): Catalog {
  return validateCatalog(parseCatalogJson(text));
}
