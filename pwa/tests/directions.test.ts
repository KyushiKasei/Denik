import { expect, test } from "vitest";
import { appleMapsDirectionsUrl, googleMapsDirectionsUrl, mapyCzDirectionsUrl } from "../src/geo/directions";
import { mapTileStatus, mapTileStatusLabel } from "../src/geo/tileStatus";

const dest = { latitude: 49.704, longitude: 16.891 };
const origin = { latitude: 50.08, longitude: 14.42 };

test("Mapy.cz trasa používá lon,lat a umí jen cíl", () => {
  expect(mapyCzDirectionsUrl(origin, dest)).toBe(
    "https://mapy.cz/fnc/v1/route?start=14.42,50.08&end=16.891,49.704",
  );
  expect(mapyCzDirectionsUrl(null, dest)).toBe("https://mapy.cz/fnc/v1/route?end=16.891,49.704");
  expect(mapyCzDirectionsUrl(origin, { latitude: 99, longitude: 0 })).toBeNull();
});

test("Apple Maps daddr / saddr", () => {
  const withOrigin = appleMapsDirectionsUrl(origin, dest, "Bouzov");
  expect(withOrigin).toContain("https://maps.apple.com/?");
  expect(withOrigin).toContain("saddr=50.08%2C14.42");
  expect(withOrigin).toContain("daddr=49.704%2C16.891");
  expect(withOrigin).toContain("q=Bouzov");
  const destOnly = appleMapsDirectionsUrl(null, dest);
  expect(destOnly).toContain("daddr=49.704%2C16.891");
  expect(destOnly).not.toContain("saddr=");
});

test("Google Maps directions origin+destination", () => {
  const withOrigin = googleMapsDirectionsUrl(origin, dest);
  expect(withOrigin).toContain("https://www.google.com/maps/dir/?");
  expect(withOrigin).toContain("origin=50.08%2C14.42");
  expect(withOrigin).toContain("destination=49.704%2C16.891");
  const destOnly = googleMapsDirectionsUrl(null, dest);
  expect(destOnly).toContain("destination=49.704%2C16.891");
  expect(destOnly).not.toContain("origin=");
});

test("stav dlaždic: online / cache / miss", () => {
  expect(mapTileStatus(true, false)).toBe("online");
  expect(mapTileStatus(true, true)).toBe("online");
  expect(mapTileStatus(false, false)).toBe("offline-cached");
  expect(mapTileStatus(false, true)).toBe("offline-miss");
  expect(mapTileStatusLabel("online")).toBe("Mapa: online");
  expect(mapTileStatusLabel("offline-cached")).toBe("Mapa: poslední stažené dlaždice (offline)");
  expect(mapTileStatusLabel("offline-miss")).toBe("Mapa: dlaždice nejsou v mezipaměti");
});
