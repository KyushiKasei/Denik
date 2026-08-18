import { expect, test } from "vitest";
import { facetCounts, filterPlaces, filtersFromParams, uniqueSorted } from "../src/catalog/filterPlaces";
import { formatTypes, isInternalReviewNote, locationLine, publicDescription } from "../src/catalog/labels";
import type { CatalogPlace } from "../src/catalog/types";

const bouzov: CatalogPlace = {
  id: "1",
  name: "Bouzov",
  short_name: null,
  alternative_names: ["Hrad Bouzov"],
  types: ["CASTLE"],
  condition: "PRESERVED",
  visitability: "REGULAR",
  short_description: null,
  heritage_status: "NKP",
  unesco: false,
  location: {
    latitude: 49.7,
    longitude: 16.8,
    address: null,
    municipality: "Bouzov",
    district: "Olomouc",
    region: "Olomoucký kraj",
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

const becov: CatalogPlace = {
  ...bouzov,
  id: "2",
  name: "Bečov",
  alternative_names: [],
  types: ["CASTLE", "CHATEAU"],
  location: {
    ...bouzov.location,
    municipality: "Bečov nad Teplou",
    district: "Karlovy Vary",
    region: "Karlovarský kraj",
  },
};

const privatePlace: CatalogPlace = {
  ...bouzov,
  id: "3",
  name: "Soukromý",
  visitability: "PRIVATE",
};

test("hledání ignoruje diakritiku", () => {
  const found = filterPlaces([bouzov, becov], { query: "becov", type: "", region: "", district: "", journal: "" });
  expect(found.map((place) => place.name)).toEqual(["Bečov"]);
});

test("hledání do dvou písmen ještě nefiltruje", () => {
  const found = filterPlaces([bouzov, becov], { query: "be", type: "", region: "", district: "", journal: "" });
  expect(found).toHaveLength(2);
});

test("filtr typu a kraje", () => {
  const found = filterPlaces([bouzov, becov], {
    query: "",
    type: "CHATEAU",
    region: "Karlovarský kraj",
    district: "",
    journal: "",
  });
  expect(found).toHaveLength(1);
  expect(found[0]?.name).toBe("Bečov");
});

test("hradozámek se v UI spojí jako hrad a zámek", () => {
  expect(formatTypes(["CASTLE", "CHATEAU"])).toBe("Hrad a zámek");
  expect(formatTypes([])).toBe("Bez typu");
  expect(formatTypes(["RUIN", "CASTLE"], { omitLabels: ["Zřícenina"] })).toBe("Hrad");
  expect(formatTypes(["RUIN"], { hideInName: "Adršpach Zřícenina" })).toBe("");
});

test("filtr přístupnosti zahrnuje skupinu přístupné veřejnosti", () => {
  const publicOnly = filterPlaces([bouzov, becov, privatePlace], {
    query: "",
    type: "",
    region: "",
    district: "",
    visitability: "PUBLIC",
    journal: "",
  });
  expect(publicOnly.map((place) => place.name)).toEqual(["Bečov", "Bouzov"]);
  const closed = filterPlaces([bouzov, privatePlace], {
    query: "",
    type: "",
    region: "",
    district: "",
    visitability: "NOT_PUBLIC",
    journal: "",
  });
  expect(closed.map((place) => place.name)).toEqual(["Soukromý"]);
});

test("počty ve filtru přístupnosti se zmenší podle jiného filtru", () => {
  const countsAll = facetCounts([bouzov, becov, privatePlace], {
    query: "",
    type: "",
    region: "",
    district: "",
    journal: "",
  });
  expect(countsAll.visitability.PUBLIC).toBe(2);
  expect(countsAll.visitability.PRIVATE).toBe(1);
  const countsType = facetCounts([bouzov, becov, privatePlace], {
    query: "",
    type: "CASTLE",
    region: "",
    district: "",
    journal: "",
  });
  expect(countsType.visitability.PUBLIC).toBe(2);
  const countsRegion = facetCounts([bouzov, becov, privatePlace], {
    query: "",
    type: "",
    region: "Karlovarský kraj",
    district: "",
    journal: "",
  });
  expect(countsRegion.visitability.PUBLIC).toBe(1);
  expect(countsRegion.visitability.PRIVATE ?? 0).toBe(0);
});

test("filtr navštíveno a chci navštívit", () => {
  const diary = {
    visitedIds: new Set(["1"]),
    wantIds: new Set(["2"]),
    favIds: new Set(["2"]),
  };
  expect(filterPlaces([bouzov, becov], { query: "", type: "", region: "", district: "", journal: "visited" }, diary).map((p) => p.name)).toEqual([
    "Bouzov",
  ]);
  expect(
    filterPlaces([bouzov, becov], { query: "", type: "", region: "", district: "", journal: "want_to_visit" }, diary).map(
      (p) => p.name,
    ),
  ).toEqual(["Bečov"]);
  expect(
    filterPlaces([bouzov, becov], { query: "", type: "", region: "", district: "", journal: "not_visited" }, diary).map(
      (p) => p.name,
    ),
  ).toEqual(["Bečov"]);
  expect(
    filterPlaces([bouzov, becov], { query: "", type: "", region: "", district: "", journal: "favorite" }, diary).map(
      (p) => p.name,
    ),
  ).toEqual(["Bečov"]);
});

test("řazení podle názvu a kraje", () => {
  const foundDesc = filterPlaces([bouzov, becov], {
    query: "",
    type: "",
    region: "",
    district: "",
    journal: "",
    sort: "name_desc",
  });
  expect(foundDesc.map((place) => place.name)).toEqual(["Bouzov", "Bečov"]);
  const byRegion = filterPlaces([bouzov, becov], {
    query: "",
    type: "",
    region: "",
    district: "",
    journal: "",
    sort: "region",
  });
  expect(byRegion.map((place) => place.name)).toEqual(["Bečov", "Bouzov"]);
});

test("filtry UNESCO, ochrany a GPS", () => {
  const unescoPlace: CatalogPlace = { ...bouzov, id: "4", name: "UNESCO", unesco: true, heritage_status: "NKP" };
  const noGps: CatalogPlace = {
    ...becov,
    id: "5",
    name: "Bez GPS",
    heritage_status: "NONE",
    location: { ...becov.location, latitude: null, longitude: null },
  };
  const places = [bouzov, unescoPlace, noGps];
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", unesco: "yes" }).map((p) => p.name),
  ).toEqual(["UNESCO"]);
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", unesco: "no" }).map((p) => p.name),
  ).toEqual(["Bez GPS", "Bouzov"]);
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", heritage: "NKP" }).map(
      (p) => p.name,
    ),
  ).toEqual(["Bouzov", "UNESCO"]);
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", gps: "without" }).map(
      (p) => p.name,
    ),
  ).toEqual(["Bez GPS"]);
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", gps: "with" }).map((p) => p.name),
  ).toEqual(["Bouzov", "UNESCO"]);
});

test("výchozí worth schová zaniklé a soukromé, nechá zříceninu", () => {
  const grass: CatalogPlace = { ...bouzov, id: "6", name: "Tráva", condition: "EXTINCT", visitability: "EXTINCT", heritage_status: "NONE" };
  const ruin: CatalogPlace = {
    ...bouzov,
    id: "7",
    name: "Trosky",
    types: ["RUIN"],
    condition: "RUIN",
    visitability: "FREE_ACCESS",
    heritage_status: "NKP",
  };
  const places = [bouzov, privatePlace, grass, ruin];
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", worth: true }).map((p) => p.name),
  ).toEqual(["Bouzov", "Trosky"]);
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", condition: "RUIN" }).map(
      (p) => p.name,
    ),
  ).toEqual(["Trosky"]);
});

test("řazení podle zajímavosti dá NKP výš", () => {
  const stub: CatalogPlace = {
    ...bouzov,
    id: "8",
    name: "Aaa stub",
    heritage_status: "NONE",
    visitability: "FREE_ACCESS",
    condition: "RUIN",
  };
  const found = filterPlaces([stub, bouzov], {
    query: "",
    type: "",
    region: "",
    district: "",
    journal: "",
    sort: "worth",
  });
  expect(found.map((place) => place.name)).toEqual(["Bouzov", "Aaa stub"]);
});

test("filtr dnes otevřeno bere 24/7 a volný přístup", () => {
  const always: CatalogPlace = { ...bouzov, id: "9", name: "Nonstop", osm_opening_hours: "24/7" };
  const closed: CatalogPlace = { ...bouzov, id: "10", name: "Zavřeno", visitability: "CLOSED" };
  const found = filterPlaces([always, closed, bouzov], {
    query: "",
    type: "",
    region: "",
    district: "",
    journal: "",
    hours: "open",
  });
  expect(found.map((p) => p.name)).toEqual(["Nonstop"]);
});

test("filtr měsíce vyřadí sezónní hrad v zimě", () => {
  const seasonal: CatalogPlace = {
    ...bouzov,
    id: "11",
    name: "Sezóna",
    visitability: "SEASONAL",
  };
  const found = filterPlaces([seasonal, bouzov], {
    query: "",
    type: "",
    region: "",
    district: "",
    journal: "",
    openMonth: 1,
  });
  expect(found.map((place) => place.name)).toEqual(["Bouzov"]);
});

test("filtr zázemí a psa", () => {
  const dog: CatalogPlace = { ...bouzov, id: "12", name: "Se psem", dogs: "yes", amenities: ["toilets"] };
  const cafe: CatalogPlace = { ...bouzov, id: "13", name: "Kavárna", amenities: ["cafe"] };
  const places = [bouzov, dog, cafe];
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", extra: "dogs" }).map((p) => p.name),
  ).toEqual(["Se psem"]);
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", extra: "toilets" }).map((p) => p.name),
  ).toEqual(["Se psem"]);
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", extra: "cafe" }).map((p) => p.name),
  ).toEqual(["Kavárna"]);
});

test("vrstva zaniklých obejde výchozí worth", () => {
  const grass: CatalogPlace = {
    ...bouzov,
    id: "14",
    name: "Tráva",
    condition: "EXTINCT",
    visitability: "EXTINCT",
    heritage_status: "NONE",
  };
  const places = [bouzov, grass];
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", worth: true }).map((p) => p.name),
  ).toEqual(["Bouzov"]);
  expect(
    filterPlaces(places, { query: "", type: "", region: "", district: "", journal: "", worth: true, lost: true }).map(
      (p) => p.name,
    ),
  ).toEqual(["Tráva"]);
  const counts = facetCounts(places, { query: "", type: "", region: "", district: "", journal: "", worth: true });
  expect(counts.lost.yes).toBe(1);
});

test("filtr slohu", () => {
  const gothic: CatalogPlace = { ...bouzov, id: "15", name: "Gotika", architectural_style: "gotika" };
  expect(
    filterPlaces([bouzov, gothic], { query: "", type: "", region: "", district: "", journal: "", style: "gotika" }).map(
      (p) => p.name,
    ),
  ).toEqual(["Gotika"]);
});

test("filtersFromParams čte společné query parametry", () => {
  const filters = filtersFromParams(new URLSearchParams("q=hrad&type=CASTLE&lost=yes&sort=worth&month=7"));
  expect(filters.query).toBe("hrad");
  expect(filters.type).toBe("CASTLE");
  expect(filters.lost).toBe(true);
  expect(filters.sort).toBe("worth");
  expect(filters.openMonth).toBe(7);
});

test("filtersFromParams zahodí neznámý typ", () => {
  expect(filtersFromParams(new URLSearchParams("type=NOPE")).type).toBe("");
});

test("sezóna teď nebere místa bez sezónních hodin", () => {
  const seasonal: CatalogPlace = {
    ...bouzov,
    id: "17",
    name: "Sezónní",
    visitability: "SEASONAL",
    osm_opening_hours: "Apr-Oct Mo-Su 09:00-17:00",
  };
  const found = filterPlaces([bouzov, seasonal], {
    query: "",
    type: "",
    region: "",
    district: "",
    journal: "",
    hours: "season",
  });
  expect(found.map((place) => place.name)).toEqual(["Sezónní"]);
});

test("slepované okresy se rozdělí a filtrují po částech", () => {
  const glued: CatalogPlace = {
    ...bouzov,
    id: "16",
    name: "Slepený",
    location: { ...bouzov.location, district: "Benešov; Mladá Boleslav" },
  };
  expect(uniqueSorted([glued.location.district, "Olomouc"])).toEqual(["Benešov", "Mladá Boleslav", "Olomouc"]);
  expect(
    filterPlaces([bouzov, glued], { query: "", type: "", region: "", district: "Benešov", journal: "" }).map(
      (place) => place.name,
    ),
  ).toEqual(["Slepený"]);
});

test("locationLine neschovává Prahu třikrát", () => {
  const prague: CatalogPlace = {
    ...bouzov,
    location: {
      ...bouzov.location,
      municipality: "Praha",
      district: "území Hlavního města Prahy",
      region: "Hlavní město Praha",
    },
  };
  expect(locationLine(prague)).toBe("Praha");
});

test("interní review poznámka nejde do veřejného popisu", () => {
  expect(isInternalReviewNote("Nejasný záznam blízko Karlštejna pro review.")).toBe(true);
  expect(publicDescription({ ...bouzov, short_description: "Nejasný záznam blízko Karlštejna pro review." })).toBeNull();
  expect(publicDescription({ ...bouzov, short_description: "Gotický hrad nad Berounkou." })).toBe(
    "Gotický hrad nad Berounkou.",
  );
});

test("typ Zřícenina bere i místo se stavem RUIN bez typu RUIN", () => {
  const byCondition: CatalogPlace = { ...bouzov, id: "ruin-cond", types: ["CASTLE"], condition: "RUIN" };
  const found = filterPlaces([bouzov, byCondition], {
    query: "",
    type: "RUIN",
    region: "",
    district: "",
    journal: "",
    worth: false,
  });
  expect(found.map((place) => place.id)).toEqual(["ruin-cond"]);
  const counts = facetCounts([bouzov, byCondition], {
    query: "",
    type: "",
    region: "",
    district: "",
    journal: "",
    worth: false,
  });
  expect(counts.types.RUIN).toBe(1);
});
