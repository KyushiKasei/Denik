export const CATALOG_VIEW_KEY = "pamatky.catalog.view";

export type CatalogView = "cards" | "list";

export function parseCatalogView(raw: string | null | undefined): CatalogView | null {
  return raw === "cards" || raw === "list" ? raw : null;
}

export function loadCatalogView(): CatalogView {
  try {
    return parseCatalogView(localStorage.getItem(CATALOG_VIEW_KEY)) ?? "cards";
  } catch {
    return "cards";
  }
}

export function saveCatalogView(view: CatalogView): void {
  try {
    localStorage.setItem(CATALOG_VIEW_KEY, view);
  } catch {
    // private mode / quota
  }
}
