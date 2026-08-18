/** ZIP bez komprese (store). Žádná závislost — diary.json + fotky. */

const CRC_TABLE = new Uint32Array(256);
for (let i = 0; i < 256; i += 1) {
  let crc = i;
  for (let j = 0; j < 8; j += 1) {
    crc = crc & 1 ? (crc >>> 1) ^ 0xedb88320 : crc >>> 1;
  }
  CRC_TABLE[i] = crc >>> 0;
}

export function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i += 1) {
    crc = CRC_TABLE[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

export interface ZipEntry {
  name: string;
  data: Uint8Array;
}

function dosTime(date: Date): { time: number; date: number } {
  const year = Math.max(1980, date.getFullYear());
  const time = (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2);
  const dosDate = ((year - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate();
  return { time, date: dosDate };
}

function u16(value: number): Uint8Array {
  const out = new Uint8Array(2);
  new DataView(out.buffer).setUint16(0, value, true);
  return out;
}

function u32(value: number): Uint8Array {
  const out = new Uint8Array(4);
  new DataView(out.buffer).setUint32(0, value, true);
  return out;
}

function concat(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

export function createZip(entries: ZipEntry[], now = new Date()): Uint8Array {
  const encoder = new TextEncoder();
  const { time, date } = dosTime(now);
  const locals: Uint8Array[] = [];
  const centrals: Uint8Array[] = [];
  let offset = 0;

  for (const entry of entries) {
    const nameBytes = encoder.encode(entry.name.replaceAll("\\", "/"));
    const crc = crc32(entry.data);
    const size = entry.data.length;
    const local = concat([
      u32(0x04034b50),
      u16(20),
      u16(0x0800),
      u16(0),
      u16(time),
      u16(date),
      u32(crc),
      u32(size),
      u32(size),
      u16(nameBytes.length),
      u16(0),
      nameBytes,
      entry.data,
    ]);
    const central = concat([
      u32(0x02014b50),
      u16(20),
      u16(20),
      u16(0x0800),
      u16(0),
      u16(time),
      u16(date),
      u32(crc),
      u32(size),
      u32(size),
      u16(nameBytes.length),
      u16(0),
      u16(0),
      u16(0),
      u16(0),
      u32(0),
      u32(offset),
      nameBytes,
    ]);
    locals.push(local);
    centrals.push(central);
    offset += local.length;
  }

  const centralDir = concat(centrals);
  const eocd = concat([
    u32(0x06054b50),
    u16(0),
    u16(0),
    u16(entries.length),
    u16(entries.length),
    u32(centralDir.length),
    u32(offset),
    u16(0),
  ]);
  return concat([...locals, centralDir, eocd]);
}

function requireBytes(data: Uint8Array, offset: number, size: number): void {
  if (offset < 0 || size < 0 || offset + size > data.length) {
    throw new Error("Soubor ZIP je poškozený.");
  }
}

function readU16(view: DataView, data: Uint8Array, offset: number): number {
  requireBytes(data, offset, 2);
  return view.getUint16(offset, true);
}

function readU32(view: DataView, data: Uint8Array, offset: number): number {
  requireBytes(data, offset, 4);
  return view.getUint32(offset, true);
}

export function readZip(data: Uint8Array): ZipEntry[] {
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  let eocd = -1;
  // ZIP komentář má max 65535 B, EOCD 22 B. Bez stropu by 80 MB bez EOCD zmrazilo UI.
  const minOffset = Math.max(0, data.length - 22 - 65535);
  for (let i = data.length - 22; i >= minOffset; i -= 1) {
    if (readU32(view, data, i) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) {
    throw new Error("Soubor ZIP není platný.");
  }
  requireBytes(data, eocd, 22);
  const count = readU16(view, data, eocd + 10);
  let offset = readU32(view, data, eocd + 16);
  const decoder = new TextDecoder();
  const entries: ZipEntry[] = [];
  for (let i = 0; i < count; i += 1) {
    requireBytes(data, offset, 46);
    if (readU32(view, data, offset) !== 0x02014b50) {
      throw new Error("Soubor ZIP je poškozený.");
    }
    const nameLen = readU16(view, data, offset + 28);
    const extraLen = readU16(view, data, offset + 30);
    const commentLen = readU16(view, data, offset + 32);
    const localOffset = readU32(view, data, offset + 42);
    requireBytes(data, offset + 46, nameLen);
    const name = decoder.decode(data.subarray(offset + 46, offset + 46 + nameLen));
    requireBytes(data, localOffset, 30);
    const method = readU16(view, data, localOffset + 8);
    if (method !== 0) {
      throw new Error("ZIP musí být bez komprese (store), jako export z této aplikace.");
    }
    const localNameLen = readU16(view, data, localOffset + 26);
    const localExtra = readU16(view, data, localOffset + 28);
    const size = readU32(view, data, localOffset + 22);
    const start = localOffset + 30 + localNameLen + localExtra;
    requireBytes(data, start, size);
    entries.push({ name, data: data.subarray(start, start + size) });
    offset += 46 + nameLen + extraLen + commentLen;
  }
  return entries;
}

export function looksLikeZip(bytes: Uint8Array): boolean {
  return bytes.length >= 4 && bytes[0] === 0x50 && bytes[1] === 0x4b;
}
