export interface PhotoExif {
  latitude: number | null;
  longitude: number | null;
  takenAt: string | null;
}

const GPS_IFD = 0x8825;
const EXIF_IFD = 0x8769;
const DATETIME_ORIGINAL = 0x9003;
const GPS_LAT_REF = 0x0001;
const GPS_LAT = 0x0002;
const GPS_LON_REF = 0x0003;
const GPS_LON = 0x0004;
const RATIONAL = 5;
const SRATIONAL = 10;

function readU16(view: DataView, offset: number, le: boolean): number {
  return view.getUint16(offset, le);
}

function readU32(view: DataView, offset: number, le: boolean): number {
  return view.getUint32(offset, le);
}

function findApp1Exif(buffer: ArrayBuffer): ArrayBuffer | null {
  const bytes = new Uint8Array(buffer);
  if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) {
    return null;
  }
  let i = 2;
  while (i + 4 < bytes.length) {
    if (bytes[i] !== 0xff) {
      i += 1;
      continue;
    }
    const marker = bytes[i + 1];
    if (marker === 0xda || marker === 0xd9) {
      break;
    }
    if (marker >= 0xd0 && marker <= 0xd7) {
      i += 2;
      continue;
    }
    if (i + 4 > bytes.length) {
      break;
    }
    const length = (bytes[i + 2] << 8) | bytes[i + 3];
    if (length < 2 || i + 2 + length > bytes.length) {
      break;
    }
    if (marker === 0xe1) {
      const start = i + 4;
      const header = bytes.subarray(start, start + 6);
      const isExif =
        header.length >= 6 &&
        header[0] === 0x45 &&
        header[1] === 0x78 &&
        header[2] === 0x69 &&
        header[3] === 0x66 &&
        header[4] === 0x00 &&
        header[5] === 0x00;
      if (isExif) {
        return buffer.slice(start + 6, i + 2 + length);
      }
    }
    i += 2 + length;
  }
  return null;
}

interface IfdEntry {
  tag: number;
  type: number;
  count: number;
  valueOffset: number;
}

function readIfd(view: DataView, offset: number, le: boolean): IfdEntry[] {
  if (offset + 2 > view.byteLength) {
    return [];
  }
  const count = readU16(view, offset, le);
  const entries: IfdEntry[] = [];
  let cursor = offset + 2;
  for (let i = 0; i < count; i += 1) {
    if (cursor + 12 > view.byteLength) {
      break;
    }
    entries.push({
      tag: readU16(view, cursor, le),
      type: readU16(view, cursor + 2, le),
      count: readU32(view, cursor + 4, le),
      valueOffset: readU32(view, cursor + 8, le),
    });
    cursor += 12;
  }
  return entries;
}

function asciiValue(view: DataView, entry: IfdEntry, tiffStart: number, le: boolean): string {
  const size = entry.count;
  let offset = entry.valueOffset;
  if (size <= 4) {
    const bytes = le
      ? [entry.valueOffset & 0xff, (entry.valueOffset >> 8) & 0xff, (entry.valueOffset >> 16) & 0xff, (entry.valueOffset >> 24) & 0xff]
      : [
          (entry.valueOffset >> 24) & 0xff,
          (entry.valueOffset >> 16) & 0xff,
          (entry.valueOffset >> 8) & 0xff,
          entry.valueOffset & 0xff,
        ];
    return String.fromCharCode(...bytes.slice(0, size)).replace(/\0+$/, "").trim();
  }
  offset = tiffStart + entry.valueOffset;
  if (offset + size > view.byteLength) {
    return "";
  }
  const chars: number[] = [];
  for (let i = 0; i < size; i += 1) {
    chars.push(view.getUint8(offset + i));
  }
  return String.fromCharCode(...chars).replace(/\0+$/, "").trim();
}

function rational(
  view: DataView,
  tiffStart: number,
  offset: number,
  index: number,
  le: boolean,
  signed: boolean,
): number | null {
  const at = tiffStart + offset + index * 8;
  if (at + 8 > view.byteLength) {
    return null;
  }
  const num = signed ? view.getInt32(at, le) : readU32(view, at, le);
  const den = readU32(view, at + 4, le);
  if (den === 0) {
    return null;
  }
  return num / den;
}

function dmsToDeg(view: DataView, entry: IfdEntry, tiffStart: number, le: boolean): number | null {
  const signed = entry.type === SRATIONAL;
  const deg = rational(view, tiffStart, entry.valueOffset, 0, le, signed);
  const min = rational(view, tiffStart, entry.valueOffset, 1, le, signed);
  const sec = rational(view, tiffStart, entry.valueOffset, 2, le, signed);
  if (deg == null || min == null || sec == null) {
    return null;
  }
  return deg + min / 60 + sec / 3600;
}

function normalizeTakenAt(raw: string): string | null {
  const match = /^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/.exec(raw);
  if (!match) {
    return null;
  }
  return `${match[1]}-${match[2]}-${match[3]}`;
}

export function parseJpegExif(buffer: ArrayBuffer): PhotoExif {
  const empty: PhotoExif = { latitude: null, longitude: null, takenAt: null };
  const tiff = findApp1Exif(buffer);
  if (!tiff || tiff.byteLength < 8) {
    return empty;
  }
  const view = new DataView(tiff);
  const byteOrder = String.fromCharCode(view.getUint8(0), view.getUint8(1));
  const le = byteOrder === "II";
  if (!le && byteOrder !== "MM") {
    return empty;
  }
  if (readU16(view, 2, le) !== 42) {
    return empty;
  }
  const ifd0 = readU32(view, 4, le);
  const entries = readIfd(view, ifd0, le);
  let takenAt: string | null = null;
  let latitude: number | null = null;
  let longitude: number | null = null;
  let latRef = "N";
  let lonRef = "E";

  const exifOffset = entries.find((entry) => entry.tag === EXIF_IFD);
  if (exifOffset) {
    const exifEntries = readIfd(view, exifOffset.valueOffset, le);
    const dateEntry = exifEntries.find((entry) => entry.tag === DATETIME_ORIGINAL);
    if (dateEntry) {
      takenAt = normalizeTakenAt(asciiValue(view, dateEntry, 0, le));
    }
  }

  const gpsOffset = entries.find((entry) => entry.tag === GPS_IFD);
  if (gpsOffset) {
    const gpsEntries = readIfd(view, gpsOffset.valueOffset, le);
    for (const entry of gpsEntries) {
      if (entry.tag === GPS_LAT_REF) {
        latRef = asciiValue(view, entry, 0, le) || latRef;
      }
      if (entry.tag === GPS_LON_REF) {
        lonRef = asciiValue(view, entry, 0, le) || lonRef;
      }
      if (entry.tag === GPS_LAT && (entry.type === RATIONAL || entry.type === SRATIONAL)) {
        latitude = dmsToDeg(view, entry, 0, le);
      }
      if (entry.tag === GPS_LON && (entry.type === RATIONAL || entry.type === SRATIONAL)) {
        longitude = dmsToDeg(view, entry, 0, le);
      }
    }
  }

  if (latitude != null && latRef.toUpperCase().startsWith("S")) {
    latitude = -latitude;
  }
  if (longitude != null && lonRef.toUpperCase().startsWith("W")) {
    longitude = -longitude;
  }
  if (latitude != null && (latitude < -90 || latitude > 90)) {
    latitude = null;
  }
  if (longitude != null && (longitude < -180 || longitude > 180)) {
    longitude = null;
  }
  return { latitude, longitude, takenAt };
}

export async function readPhotoExif(file: Blob): Promise<PhotoExif> {
  const buffer = await file.arrayBuffer();
  return parseJpegExif(buffer);
}
