export class DiaryImportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DiaryImportError";
  }
}
