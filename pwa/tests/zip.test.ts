import { expect, test } from "vitest";
import { inspectIncomingFile, MAX_INCOMING_BYTES } from "../src/diary/fileIntake";
import { createZip, crc32, looksLikeZip, readZip } from "../src/diary/zip";

test("crc32 prázdných dat je známá hodnota", () => {
  expect(crc32(new Uint8Array())).toBe(0);
});

test("zip store a zpětné čtení", () => {
  const payload = new TextEncoder().encode('{"ok":true}\n');
  const zip = createZip([
    { name: "diary.json", data: payload },
    { name: "photos/0198f23a-5e5e-7b31-a8be-8c99507a2140/0198f23a-5e5e-7b31-a8be-8c99507a2141.jpg", data: new Uint8Array([1, 2, 3]) },
  ]);
  expect(looksLikeZip(zip)).toBe(true);
  const entries = readZip(zip);
  expect(entries.map((entry) => entry.name)).toEqual([
    "diary.json",
    "photos/0198f23a-5e5e-7b31-a8be-8c99507a2140/0198f23a-5e5e-7b31-a8be-8c99507a2141.jpg",
  ]);
  expect(new TextDecoder().decode(entries[0].data)).toContain('"ok"');
  expect([...entries[1].data]).toEqual([1, 2, 3]);
});

test("zip s kompresí se odmítne", () => {
  const zip = createZip([{ name: "diary.json", data: new TextEncoder().encode("{}\n") }]);
  zip[8] = 8;
  zip[9] = 0;
  expect(() => readZip(zip)).toThrow(/bez komprese/);
});

test("poškozený zip s krátkými daty se odmítne", () => {
  const zip = createZip([{ name: "diary.json", data: new TextEncoder().encode("{}\n") }]);
  expect(() => readZip(zip.subarray(0, 12))).toThrow(/ZIP/);
});

test("falešné EOCD mimo okno komentáře se ignoruje", () => {
  const junk = new Uint8Array(80 * 1024);
  new DataView(junk.buffer).setUint32(0, 0x06054b50, true);
  expect(() => readZip(junk)).toThrow(/ZIP/);
});

test("soubor nad 80 MB se před čtením odmítne", async () => {
  const file = new File([new Uint8Array([1, 2, 3])], "diary.zip");
  Object.defineProperty(file, "size", { value: MAX_INCOMING_BYTES + 1 });
  await expect(inspectIncomingFile(file)).rejects.toThrow(/80 MB/);
});

test("diary.json v ZIP nad 20 MB se odmítne", async () => {
  const zip = createZip([{ name: "diary.json", data: new Uint8Array(20 * 1024 * 1024 + 1) }]);
  const file = new File([zip], "diary.zip", { type: "application/zip" });
  await expect(inspectIncomingFile(file)).rejects.toThrow(/moc velký/);
});
