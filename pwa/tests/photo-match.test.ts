import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";
import type { CatalogPlace, StoredVisit } from "../src/catalog/types";
import { parseJpegExif } from "../src/diary/exif";
import { defaultPhotoVisitChoice, matchExifToPlace, suggestPhotoMatches } from "../src/diary/photoMatch";

function place(id: string, name: string, lat: number, lon: number): CatalogPlace {
  return {
    id,
    name,
    short_name: null,
    alternative_names: [],
    types: ["CASTLE"],
    condition: "PRESERVED",
    visitability: "REGULAR",
    short_description: null,
    heritage_status: null,
    unesco: false,
    location: {
      latitude: lat,
      longitude: lon,
      address: null,
      municipality: name,
      district: null,
      region: null,
      country: "CZ",
    },
    links: {
      official: null,
      wikipedia: null,
      wikidata: null,
      heritage_catalog: null,
      opening_hours: null,
      tickets: null,
    },
    image: null,
  };
}

function degToDms(deg: number): Array<[number, number]> {
  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const minFloat = (abs - d) * 60;
  const m = Math.floor(minFloat);
  const s = (minFloat - m) * 60;
  return [
    [d, 1],
    [m, 1],
    [Math.round(s * 10000), 10000],
  ];
}

function asciiInline(text: string, le: boolean): number {
  const bytes = [text.charCodeAt(0) || 0, 0, 0, 0];
  if (le) {
    return bytes[0] | (bytes[1] << 8) | (bytes[2] << 16) | (bytes[3] << 24);
  }
  return (bytes[0] << 24) | (bytes[1] << 16) | (bytes[2] << 8) | bytes[3];
}

function writeIfdEntry(view: DataView, at: number, tag: number, type: number, count: number, value: number, le: boolean) {
  view.setUint16(at, tag, le);
  view.setUint16(at + 2, type, le);
  view.setUint32(at + 4, count, le);
  view.setUint32(at + 8, value, le);
}

function writeRationals(view: DataView, at: number, pairs: Array<[number, number]>, le: boolean) {
  pairs.forEach(([num, den], index) => {
    view.setUint32(at + index * 8, num, le);
    view.setUint32(at + index * 8 + 4, den, le);
  });
}

/** Minimální JPEG s GPS IFD včetně výšky (tag 5) — regress proti záměně délky za altitude. */
function jpegWithGps(lat: number, lon: number, le: boolean): ArrayBuffer {
  const tiff = new Uint8Array(140);
  const view = new DataView(tiff.buffer);
  tiff[0] = le ? 0x49 : 0x4d;
  tiff[1] = le ? 0x49 : 0x4d;
  view.setUint16(2, 42, le);
  view.setUint32(4, 8, le);
  view.setUint16(8, 1, le);
  writeIfdEntry(view, 10, 0x8825, 4, 1, 26, le);
  view.setUint32(22, 0, le);

  view.setUint16(26, 5, le);
  writeIfdEntry(view, 28, 0x0001, 2, 2, asciiInline(lat >= 0 ? "N" : "S", le), le);
  writeIfdEntry(view, 40, 0x0002, 5, 3, 92, le);
  writeIfdEntry(view, 52, 0x0003, 2, 2, asciiInline(lon >= 0 ? "E" : "W", le), le);
  writeIfdEntry(view, 64, 0x0004, 5, 3, 116, le);
  writeIfdEntry(view, 76, 0x0005, 1, 1, 0, le);
  view.setUint32(88, 0, le);
  writeRationals(view, 92, degToDms(lat), le);
  writeRationals(view, 116, degToDms(lon), le);

  const app1Len = 2 + 6 + tiff.length;
  const jpeg = new Uint8Array(2 + 2 + app1Len + 2);
  jpeg[0] = 0xff;
  jpeg[1] = 0xd8;
  jpeg[2] = 0xff;
  jpeg[3] = 0xe1;
  jpeg[4] = (app1Len >> 8) & 0xff;
  jpeg[5] = app1Len & 0xff;
  jpeg.set([0x45, 0x78, 0x69, 0x66, 0x00, 0x00], 6);
  jpeg.set(tiff, 12);
  jpeg[12 + tiff.length] = 0xff;
  jpeg[13 + tiff.length] = 0xd9;
  return jpeg.buffer;
}

test("EXIF GPS přiřadí nejbližší místo do 500 m", () => {
  const bouzov = place("1", "Bouzov", 49.704, 16.891);
  const prague = place("2", "Praha", 50.087, 14.421);
  const hit = matchExifToPlace([prague, bouzov], { latitude: 49.7042, longitude: 16.8912, takenAt: "2026-08-18" });
  expect(hit?.place.name).toBe("Bouzov");
  expect(hit?.km ?? 1).toBeLessThan(0.05);
});

test("bez GPS se místo nehádá", () => {
  const bouzov = place("1", "Bouzov", 49.704, 16.891);
  expect(matchExifToPlace([bouzov], { latitude: null, longitude: null, takenAt: "2026-08-18" })).toBeNull();
});

test("ne-JPEG vrátí prázdný EXIF", () => {
  const buffer = new TextEncoder().encode("not a jpeg").buffer;
  expect(parseJpegExif(buffer)).toEqual({ latitude: null, longitude: null, takenAt: null });
});

test("JPEG EXIF čte délku z tagu 4, ne výšku z tagu 5", () => {
  const little = parseJpegExif(jpegWithGps(49.704, 16.891, true));
  expect(little.latitude ?? 0).toBeCloseTo(49.704, 4);
  expect(little.longitude ?? 0).toBeCloseTo(16.891, 4);
  const big = parseJpegExif(jpegWithGps(49.592483, 17.272264, false));
  expect(big.latitude ?? 0).toBeCloseTo(49.592483, 4);
  expect(big.longitude ?? 0).toBeCloseTo(17.272264, 4);
});

test("místo 0,5–2 km se jen navrhne, nepředvybere", () => {
  const hrad = place("1", "Olomoucký hrad", 49.5942, 17.2804);
  const file = { name: "olomouc.jpg" } as File;
  const rows = suggestPhotoMatches([file], [hrad], [{ latitude: 49.598244, longitude: 17.271981, takenAt: "2026-01-20" }]);
  expect(rows[0]?.place?.name).toBe("Olomoucký hrad");
  expect(rows[0]?.confident).toBe(false);
  expect(rows[0]?.km ?? 0).toBeGreaterThan(0.5);
  expect(rows[0]?.km ?? 9).toBeLessThan(2);
});

test("místo do 500 m se předvybere", () => {
  const bouzov = place("1", "Bouzov", 49.704, 16.891);
  const file = { name: "u-hradu.jpg" } as File;
  const rows = suggestPhotoMatches([file], [bouzov], [{ latitude: 49.7042, longitude: 16.8912, takenAt: "2026-08-18" }]);
  expect(rows[0]?.confident).toBe(true);
  expect(rows[0]?.place?.name).toBe("Bouzov");
});

const sampleJpeg = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../_Denik/2026-01-15 15.06.20.jpg");

test.skipIf(!existsSync(sampleJpeg))("Samsung JPEG z _Denik má GPS Olomouc", () => {
  const buf = readFileSync(sampleJpeg);
  const exif = parseJpegExif(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
  expect(exif.takenAt).toBe("2026-01-15");
  expect(exif.latitude ?? 0).toBeCloseTo(49.592483, 4);
  expect(exif.longitude ?? 0).toBeCloseTo(17.272264, 4);
});

function visit(id: string, placeId: string, day: string, createdAt = `${day}T12:00:00+02:00`): StoredVisit {
  return {
    id,
    place_id: placeId,
    visited_at: day,
    rating: null,
    people: [],
    note: null,
    trip_id: null,
    created_at: createdAt,
    updated_at: createdAt,
    deleted_at: null,
  };
}

test("návštěva ve stejný den z EXIF má přednost", () => {
  const choice = defaultPhotoVisitChoice(
    [visit("old", "p1", "2026-08-17"), visit("same", "p1", "2026-01-15"), visit("today", "p1", "2026-08-18")],
    "p1",
    "2026-01-15",
    "2026-08-18",
  );
  expect(choice).toEqual({ kind: "existing", visitId: "same" });
});

test("když ten den návštěva není, výchozí je dnešní", () => {
  const choice = defaultPhotoVisitChoice(
    [visit("old", "p1", "2026-08-17"), visit("today", "p1", "2026-08-18")],
    "p1",
    "2026-01-15",
    "2026-08-18",
  );
  expect(choice).toEqual({ kind: "existing", visitId: "today" });
});

test("když dnes návštěva není, výchozí je poslední", () => {
  const choice = defaultPhotoVisitChoice(
    [visit("older", "p1", "2026-08-10"), visit("last", "p1", "2026-08-17")],
    "p1",
    "2026-01-15",
    "2026-08-18",
  );
  expect(choice).toEqual({ kind: "existing", visitId: "last" });
});

test("bez návštěv se nabízí nová s datem z fotky", () => {
  const choice = defaultPhotoVisitChoice([], "p1", "2026-01-15", "2026-08-18");
  expect(choice).toEqual({ kind: "create", visitedAt: "2026-01-15" });
});

test("návštěva jiného místa se nenabízí", () => {
  const choice = defaultPhotoVisitChoice([visit("other", "p2", "2026-08-18")], "p1", "2026-01-15", "2026-08-18");
  expect(choice).toEqual({ kind: "create", visitedAt: "2026-01-15" });
});
