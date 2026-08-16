import { expect, test } from "vitest";
import { DEFAULT_RADIUS_KM, MIN_RADIUS_KM } from "../src/geo/haversine";
import {
  formatGpsAccuracy,
  loadStoredMapView,
  MAP_LAST_ORIGIN_KEY,
  originFromUrlParams,
  parseStoredMapView,
  saveStoredMapView,
  urlHasCoords,
  urlHasRadius,
} from "../src/geo/mapOriginStore";

test("urlHasCoords vyžaduje obě souřadnice", () => {
  expect(urlHasCoords(new URLSearchParams("lat=49.7&lon=16.8"))).toBe(true);
  expect(urlHasCoords(new URLSearchParams("lat=49.7"))).toBe(false);
  expect(urlHasCoords(new URLSearchParams("q=Bouzov"))).toBe(false);
  expect(urlHasCoords(new URLSearchParams("lat=foo&lon=1"))).toBe(false);
  expect(urlHasCoords(new URLSearchParams("lat=0&lon=0"))).toBe(false);
});

test("originFromUrlParams neplete Number(null) s GPS 0,0", () => {
  expect(originFromUrlParams(null, null, null)).toBeNull();
  expect(originFromUrlParams("", "", null)).toBeNull();
  expect(originFromUrlParams("0", "0", "nula")).toBeNull();
  expect(originFromUrlParams("49.704", "16.891", " Bouzov ")).toEqual({
    latitude: 49.704,
    longitude: 16.891,
    label: "Bouzov",
    source: "coords",
  });
});

test("urlHasRadius pozná slider v URL", () => {
  expect(urlHasRadius(new URLSearchParams("radius_km=20"))).toBe(true);
  expect(urlHasRadius(new URLSearchParams("lat=1"))).toBe(false);
});

test("parseStoredMapView odmítne neplatné souřadnice", () => {
  expect(parseStoredMapView(null)).toBeNull();
  expect(parseStoredMapView("{")).toBeNull();
  expect(parseStoredMapView(JSON.stringify({ latitude: 99, longitude: 16 }))).toBeNull();
  expect(parseStoredMapView(JSON.stringify({ latitude: 0, longitude: 0, label: "0.00000, 0.00000" }))).toBeNull();
  const ok = parseStoredMapView(
    JSON.stringify({ latitude: 49.704, longitude: 16.891, label: "Bouzov", source: "place", radiusKm: 3 }),
  );
  expect(ok?.label).toBe("Bouzov");
  expect(ok?.source).toBe("place");
  expect(ok?.radiusKm).toBe(MIN_RADIUS_KM);
});

test("save a load last origin v localStorage", () => {
  saveStoredMapView({
    latitude: 50.08,
    longitude: 14.42,
    label: "Praha",
    source: "nominatim",
    radiusKm: 40,
  });
  const loaded = loadStoredMapView();
  expect(loaded).toEqual({
    latitude: 50.08,
    longitude: 14.42,
    label: "Praha",
    source: "nominatim",
    radiusKm: 40,
  });
  expect(localStorage.getItem(MAP_LAST_ORIGIN_KEY)).toContain("Praha");
  saveStoredMapView({
    latitude: 49.2,
    longitude: 16.6,
    label: "  ",
    radiusKm: DEFAULT_RADIUS_KM,
  });
  expect(loadStoredMapView()?.label).toMatch(/^49\.2/);
});

test("formatGpsAccuracy", () => {
  expect(formatGpsAccuracy(null)).toBeNull();
  expect(formatGpsAccuracy(-1)).toBeNull();
  expect(formatGpsAccuracy(24.6)).toBe("±25 m");
});
