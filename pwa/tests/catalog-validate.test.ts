import { expect, test } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CatalogImportError } from "../src/catalog/errors";
import { loadCatalogFromText, validateCatalog } from "../src/catalog/validate";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const sampleText = readFileSync(path.join(repoRoot, "fixtures/catalog.sample.json"), "utf8");

function sampleCatalog() {
  return JSON.parse(sampleText) as Record<string, unknown>;
}

test("validní catalog.sample.json se načte", () => {
  const catalog = loadCatalogFromText(sampleText);
  expect(catalog.schema_version).toBe(1);
  expect(catalog.places[0]?.name).toBe("Bouzov");
  expect(catalog.places[0]?.id).toBe("0198f23a-5e5e-7b31-a8be-8c99507a2138");
});

test("nevalidní soubor se odmítne", () => {
  const invalid = { ...sampleCatalog(), places: "ne" };
  expect(() => validateCatalog(invalid)).toThrow(CatalogImportError);
  expect(() => validateCatalog(invalid)).toThrow(/Nevalidní catalog\.json/);
});

test("neznámá schema_version se odmítne", () => {
  const unknown = { ...sampleCatalog(), schema_version: 2 };
  expect(() => validateCatalog(unknown)).toThrow(CatalogImportError);
  expect(() => validateCatalog(unknown)).toThrow(/schema_version/);
});

test("chybějící schema_version se odmítne", () => {
  const missing = sampleCatalog();
  delete missing.schema_version;
  expect(() => validateCatalog(missing)).toThrow(/schema_version/);
});

test("ne-JSON text se odmítne", () => {
  expect(() => loadCatalogFromText("{")).toThrow(/není platný JSON/);
});

test("duplicitní places[].id se odmítne", () => {
  const data = sampleCatalog();
  const places = data.places as Array<Record<string, unknown>>;
  places.push({ ...places[0] });
  expect(() => validateCatalog(data)).toThrow(/Duplicitní places\[\]\.id/);
});

test("místo bez GPS projde schématem", () => {
  const data = sampleCatalog();
  const places = data.places as Array<Record<string, unknown>>;
  const location = { ...(places[0].location as Record<string, unknown>), latitude: null, longitude: null };
  places[0] = { ...places[0], location };
  const catalog = validateCatalog(data);
  expect(catalog.places[0]?.location.latitude).toBeNull();
});
