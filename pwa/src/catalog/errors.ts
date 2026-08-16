export class CatalogImportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CatalogImportError";
  }
}
