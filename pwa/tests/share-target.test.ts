import { expect, test } from "vitest";
import { parseSharedGeo, shareQueryFromLocation } from "../src/geo/shareTarget";

test("Mapy.cz x/y", () => {
  const geo = parseSharedGeo("https://mapy.cz/zakladni?x=16.891&y=49.704&z=16");
  expect(geo).toEqual({ latitude: 49.704, longitude: 16.891, label: "Mapy.cz" });
});

test("Google Maps @lat,lon", () => {
  const geo = parseSharedGeo("https://www.google.com/maps/place/Bouzov/@49.704,16.891,17z");
  expect(geo).toEqual({ latitude: 49.704, longitude: 16.891, label: "Google Maps" });
});

test("Apple Maps ll= a geo:", () => {
  expect(parseSharedGeo("https://maps.apple.com/?ll=49.704,16.891&q=Bouzov")).toMatchObject({
    latitude: 49.704,
    longitude: 16.891,
  });
  expect(parseSharedGeo("geo:49.704,16.891")).toEqual({ latitude: 49.704, longitude: 16.891, label: "geo" });
});

test("holé souřadnice v textu", () => {
  const geo = parseSharedGeo("49.704, 16.891 hrad");
  expect(geo?.latitude).toBe(49.704);
  expect(geo?.longitude).toBe(16.891);
});

test("nesmysl vrátí null", () => {
  expect(parseSharedGeo("https://example.com/place")).toBeNull();
  expect(parseSharedGeo("")).toBeNull();
});

test("shareQueryFromLocation čte title/text/url", () => {
  const encoded = encodeURIComponent("https://mapy.cz/?x=16.8&y=49.7");
  expect(shareQueryFromLocation(`title=Hrad&url=${encoded}`)).toEqual({
    title: "Hrad",
    text: "",
    url: "https://mapy.cz/?x=16.8&y=49.7",
  });
});
