/** Sdílené skládání textu pro hledání (katalog i Poblíž). */

export function fold(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase("cs");
}
