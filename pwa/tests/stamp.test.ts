import { expect, test } from "vitest";
import { addVisit, createTripFromPlaces, loadPlaceState, loadVisitsForPlace, savePlaceState } from "../src/diary/store";
import { completeTrip } from "../src/diary/completeTrip";
import { stampVisitToday } from "../src/diary/stamp";
import { todayIsoDate } from "../src/diary/ids";

test("razítko založí dnešní návštěvu jen jednou", async () => {
  const placeId = "0198f23a-5e5e-7b31-a8be-8c99507a2140";
  const first = await stampVisitToday(placeId);
  expect(first.created).toBe(true);
  expect(first.visit.visited_at).toBe(todayIsoDate());
  expect(first.visit.place_id).toBe(placeId);
  const second = await stampVisitToday(placeId);
  expect(second.created).toBe(false);
  expect(second.visit.id).toBe(first.visit.id);
  expect(await loadVisitsForPlace(placeId)).toHaveLength(1);
});

test("souběžné razítko stejného dne založí jednu návštěvu", async () => {
  const placeId = "0198f23a-5e5e-7b31-a8be-8c99507a2142";
  const [first, second] = await Promise.all([stampVisitToday(placeId), stampVisitToday(placeId)]);
  expect(first.visit.id).toBe(second.visit.id);
  expect([first.created, second.created].filter(Boolean)).toHaveLength(1);
  expect(await loadVisitsForPlace(placeId)).toHaveLength(1);
});

test("souběžné razítko s jiným tripId založí jednu návštěvu", async () => {
  const placeId = "0198f23a-5e5e-7b31-a8be-8c99507a2144";
  const [first, second] = await Promise.all([
    stampVisitToday(placeId),
    stampVisitToday(placeId, "0198f93b-618d-762f-a589-ccf375139dd8"),
  ]);
  expect(first.visit.id).toBe(second.visit.id);
  expect([first.created, second.created].filter(Boolean)).toHaveLength(1);
  expect(await loadVisitsForPlace(placeId)).toHaveLength(1);
});

test("doražení razítek nenaduplikuje návštěvu už v IndexedDB", async () => {
  const placeId = "0198f23a-5e5e-7b31-a8be-8c99507a2145";
  const today = todayIsoDate();
  const trip = await createTripFromPlaces({ name: "Okruh", planned_on: today, placeIds: [placeId] });
  await addVisit({ place_id: placeId, visited_at: today, rating: null, people: "", note: null });
  const result = await completeTrip(trip, new Map(), [], today, { stampMissing: true });
  expect(result.stamped).toBe(0);
  expect(await loadVisitsForPlace(placeId)).toHaveLength(1);
});

test("starší návštěva stejného místa razítku nebrání", async () => {
  const placeId = "0198f23a-5e5e-7b31-a8be-8c99507a2141";
  await addVisit({ place_id: placeId, visited_at: "2020-01-01", rating: null, people: "", note: null });
  const stamped = await stampVisitToday(placeId);
  expect(stamped.created).toBe(true);
  expect(await loadVisitsForPlace(placeId)).toHaveLength(2);
});

test("razítko s tripId doplní výlet k dnešní návštěvě bez trip_id", async () => {
  const placeId = "0198f23a-5e5e-7b31-a8be-8c99507a2146";
  const tripId = "0198f93b-618d-762f-a589-ccf375139dd9";
  const first = await stampVisitToday(placeId);
  expect(first.visit.trip_id).toBeNull();
  const second = await stampVisitToday(placeId, tripId);
  expect(second.created).toBe(false);
  expect(second.visit.id).toBe(first.visit.id);
  expect(second.visit.trip_id).toBe(tripId);
});

test("razítko s jiným tripId nepřepíše existující výlet", async () => {
  const placeId = "0198f23a-5e5e-7b31-a8be-8c99507a2147";
  const tripA = "0198f93b-618d-762f-a589-ccf375139dda";
  const tripB = "0198f93b-618d-762f-a589-ccf375139ddb";
  await stampVisitToday(placeId, tripA);
  const second = await stampVisitToday(placeId, tripB);
  expect(second.created).toBe(false);
  expect(second.visit.trip_id).toBe(tripA);
});

test("uzavření výletu nepřepíše trip_id starší návštěvy", async () => {
  const placeId = "0198f23a-5e5e-7b31-a8be-8c99507a2148";
  const today = todayIsoDate();
  const oldTrip = await createTripFromPlaces({ name: "Loni", planned_on: "2020-01-01", placeIds: [placeId] });
  const old = await addVisit({
    place_id: placeId,
    visited_at: "2020-01-01",
    rating: null,
    people: "",
    note: null,
    trip_id: oldTrip.id,
  });
  const trip = await createTripFromPlaces({ name: "Dnes", planned_on: today, placeIds: [placeId] });
  await completeTrip(trip, new Map(), [old], today, { stampMissing: false });
  const rows = await loadVisitsForPlace(placeId);
  expect(rows).toHaveLength(1);
  expect(rows[0]?.trip_id).toBe(oldTrip.id);
});

test("doražení razítek založí dnešní návštěvu vedle starší", async () => {
  const placeId = "0198f23a-5e5e-7b31-a8be-8c99507a2149";
  const today = todayIsoDate();
  const oldTrip = await createTripFromPlaces({ name: "Loni", planned_on: "2020-01-01", placeIds: [placeId] });
  await addVisit({
    place_id: placeId,
    visited_at: "2020-01-01",
    rating: null,
    people: "",
    note: null,
    trip_id: oldTrip.id,
  });
  const trip = await createTripFromPlaces({ name: "Dnes", planned_on: today, placeIds: [placeId] });
  const result = await completeTrip(trip, new Map(), [], today, { stampMissing: true });
  expect(result.stamped).toBe(1);
  const rows = await loadVisitsForPlace(placeId);
  expect(rows).toHaveLength(2);
  expect(rows.find((row) => row.visited_at === "2020-01-01")?.trip_id).toBe(oldTrip.id);
  expect(rows.find((row) => row.visited_at === today)?.trip_id).toBe(trip.id);
});

test("razítko odškrtne chci navštívit", async () => {
  const placeId = "0198f23a-5e5e-7b31-a8be-8c99507a2143";
  await savePlaceState(placeId, { want_to_visit: true });
  expect((await loadPlaceState(placeId))?.want_to_visit).toBe(true);
  await stampVisitToday(placeId);
  expect((await loadPlaceState(placeId))?.want_to_visit).toBe(false);
});

test("razítko ořeže mezery u data jako Python", async () => {
  const placeId = "0198f23a-5e5e-7b31-a8be-8c99507a214a";
  const today = todayIsoDate();
  await addVisit({ place_id: placeId, visited_at: ` ${today} `, rating: null, people: "", note: null });
  const second = await stampVisitToday(placeId);
  expect(second.created).toBe(false);
  expect(await loadVisitsForPlace(placeId)).toHaveLength(1);
});
