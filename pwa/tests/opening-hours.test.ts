import { expect, test } from "vitest";
import {
  evaluateOpeningHours,
  formatOpeningHours,
  hoursBadgeLabel,
  isClosedOnDate,
  isSeasonallyClosed,
  isSeasonallyLikelyClosed,
  dayOpenState,
  minutesUntilClose,
  parseHoursParam,
  placeOpenState,
} from "../src/catalog/openingHours";
import type { CatalogPlace } from "../src/catalog/types";

const tuesdayMorning = new Date("2026-08-18T10:00:00");
const tuesdayNight = new Date("2026-08-18T21:00:00");
const january = new Date("2026-01-15T12:00:00");
const july = new Date("2026-07-15T12:00:00");

function stub(over: Partial<CatalogPlace> = {}): CatalogPlace {
  return {
    id: "1",
    name: "Test",
    short_name: null,
    alternative_names: [],
    types: ["CASTLE"],
    condition: "PRESERVED",
    visitability: "REGULAR",
    short_description: null,
    heritage_status: null,
    unesco: false,
    location: {
      latitude: 49.7,
      longitude: 16.8,
      address: null,
      municipality: "X",
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
    ...over,
  };
}

test("24/7 je vždy otevřeno", () => {
  expect(evaluateOpeningHours("24/7", tuesdayNight)).toBe("open");
});

test("Mo-Su 09:00-16:00 dopoledne otevřeno, večer zavřeno", () => {
  expect(evaluateOpeningHours("Mo-Su 09:00-16:00", tuesdayMorning)).toBe("open");
  expect(evaluateOpeningHours("Mo-Su 09:00-16:00", tuesdayNight)).toBe("closed");
});

test("sezónní Apr-Oct je v lednu zavřeno", () => {
  const hours = "Apr-Oct Mo-Su 09:00-17:00";
  expect(isSeasonallyClosed(hours, january)).toBe(true);
  expect(isSeasonallyClosed(hours, july)).toBe(false);
  expect(evaluateOpeningHours(hours, july)).toBe("open");
});

test("Oct-Apr off zavře zimu", () => {
  const hours = "May-Sep: Mo-Su 09:00-17:00; Oct-Apr: off";
  expect(evaluateOpeningHours(hours, january)).toBe("closed");
  expect(evaluateOpeningHours(hours, july)).toBe("open");
});

test("prázdné hodiny jsou unknown, volný přístup zachovalého místa otevřený", () => {
  expect(placeOpenState(stub())).toBe("unknown");
  expect(placeOpenState(stub({ visitability: "FREE_ACCESS" }))).toBe("open");
  expect(placeOpenState(stub({ visitability: "CLOSED" }))).toBe("closed");
  expect(placeOpenState(stub({ visitability: "FREE_ACCESS", condition: "RUIN", types: ["RUIN"] }))).toBe("unknown");
});

test("SEASONAL bez hodin je v zimě mimo sezónu", () => {
  const place = stub({ visitability: "SEASONAL" });
  expect(isSeasonallyLikelyClosed(place, january)).toBe(true);
  expect(isSeasonallyLikelyClosed(place, july)).toBe(false);
});

test("čitelné hodiny a zavírá za X min", () => {
  expect(formatOpeningHours("Mo-Su 09:00-16:00")).toBe("denně 9:00–16:00");
  expect(minutesUntilClose("Mo-Su 09:00-16:00", new Date("2026-08-18T15:20:00"))).toBe(40);
  expect(hoursBadgeLabel("open", { minutesUntilClose: 40 })).toBe("zavírá za 40 min");
});

test("Apr-Oct je v lednu ten den zavřeno", () => {
  const place = stub({ osm_opening_hours: "Apr-Oct Mo-Su 09:00-17:00" });
  expect(isClosedOnDate(place, january)).toBe(true);
  expect(isClosedOnDate(place, july)).toBe(false);
  expect(dayOpenState(place, july)).toBe("open");
});

test("parseHoursParam čte open/season z URL", () => {
  expect(parseHoursParam("OPEN")).toBe("open");
  expect(parseHoursParam(" Season ")).toBe("season");
  expect(parseHoursParam("nope")).toBe("");
  expect(parseHoursParam(null)).toBe("");
});
