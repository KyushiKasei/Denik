import { expect, test } from "vitest";
import { loadCatalogView, parseCatalogView, saveCatalogView } from "../src/catalog/viewMode";

test("parseCatalogView přijme jen cards/list", () => {
  expect(parseCatalogView("cards")).toBe("cards");
  expect(parseCatalogView("list")).toBe("list");
  expect(parseCatalogView("grid")).toBeNull();
  expect(parseCatalogView(null)).toBeNull();
});

test("výchozí zobrazení jsou karty", () => {
  expect(loadCatalogView()).toBe("cards");
});

test("saveCatalogView zapíše do localStorage", () => {
  saveCatalogView("list");
  expect(loadCatalogView()).toBe("list");
  saveCatalogView("cards");
  expect(loadCatalogView()).toBe("cards");
});
