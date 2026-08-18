import type { Diary } from "./types";
import { looksLikeZip, readZip } from "./zip";

export type IncomingKind = "catalog" | "diary" | "diary-zip" | "unknown";

export interface InspectedIncoming {
  kind: IncomingKind;
  diary?: Diary;
  catalogText?: string;
  zipEntries?: Array<{ name: string; data: Uint8Array }>;
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

export function classifyJson(parsed: unknown): IncomingKind {
  const data = asObject(parsed);
  if (!data) {
    return "unknown";
  }
  if (Array.isArray(data.visits) && Array.isArray(data.place_states)) {
    return "diary";
  }
  if (Array.isArray(data.places) && typeof data.catalog_version === "number") {
    return "catalog";
  }
  return "unknown";
}

export const MAX_INCOMING_BYTES = 80 * 1024 * 1024;
export const MAX_DIARY_JSON_BYTES = 20 * 1024 * 1024;

function requireDiaryJsonSize(bytes: number): void {
  if (bytes > MAX_DIARY_JSON_BYTES) {
    throw new Error("diary.json je moc velký.");
  }
}

function looksLikeDiaryJsonHead(head: string): boolean {
  return /"visits"\s*:/.test(head) && /"place_states"\s*:/.test(head);
}

export async function inspectIncomingFile(file: File): Promise<InspectedIncoming> {
  if (file.size > MAX_INCOMING_BYTES) {
    throw new Error("Soubor je větší než 80 MB.");
  }
  const buffer = new Uint8Array(await file.arrayBuffer());
  if (looksLikeZip(buffer) || file.name.toLowerCase().endsWith(".zip")) {
    const entries = readZip(buffer);
    const diaryEntry = entries.find((entry) => entry.name.replaceAll("\\", "/").split("/").pop() === "diary.json");
    if (!diaryEntry) {
      return { kind: "unknown", zipEntries: entries };
    }
    requireDiaryJsonSize(diaryEntry.data.byteLength);
    const text = new TextDecoder().decode(diaryEntry.data);
    const { loadDiaryFromText } = await import("./validate");
    return { kind: "diary-zip", diary: loadDiaryFromText(text), zipEntries: entries };
  }
  const head = new TextDecoder().decode(buffer.subarray(0, Math.min(buffer.byteLength, 2048)));
  if (buffer.byteLength > MAX_DIARY_JSON_BYTES && looksLikeDiaryJsonHead(head)) {
    requireDiaryJsonSize(buffer.byteLength);
  }
  const text = new TextDecoder().decode(buffer);
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { kind: "unknown" };
  }
  const kind = classifyJson(parsed);
  if (kind === "diary") {
    const { loadDiaryFromText } = await import("./validate");
    return { kind, diary: loadDiaryFromText(text) };
  }
  if (kind === "catalog") {
    return { kind, catalogText: text };
  }
  return { kind: "unknown" };
}
