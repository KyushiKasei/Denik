import { expect, test } from "vitest";
import { facetCounts, filterPlaces } from "../src/catalog/filterPlaces";
import { formatTypes } from "../src/catalog/labels";
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
