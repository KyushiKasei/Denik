import { expect, test } from "vitest";
import { collapseFamilyVisits, mergeNotes, mergePeople, reassignPhotos, unionFamilyStates } from "../src/diary/familyMerge";
import type { StoredVisit } from "../src/catalog/types";
import type { StoredVisitPhoto } from "../src/diary/types";

function visit(id: string, extra: Partial<StoredVisit> = {}): StoredVisit {
  return {
    id,
    place_id: "place-1",
    visited_at: "2026-08-09",
    rating: null,
    people: [],
    note: null,
    created_at: "2026-08-09T10:00:00+02:00",
    updated_at: "2026-08-09T10:00:00+02:00",
    deleted_at: null,
    ...extra,
  };
}

test("mergePeople a mergeNotes spojí bez duplicit", () => {
  expect(mergePeople(["Jana", "Petr"], ["petr", "Eva"])).toEqual(["Jana", "Petr", "Eva"]);
  expect(mergeNotes("A", "B")).toBe("A · B");
  expect(mergeNotes("A", "a")).toBe("A");
});

test("collapseFamilyVisits sloučí stejné místo a den", () => {
  const a = visit("a", { people: ["Jana"], note: "A", rating: 4 });
  const b = visit("b", { people: ["Petr"], note: "B", rating: 5, created_at: "2026-08-09T12:00:00+02:00" });
  const { next, collapsed, photoMoves } = collapseFamilyVisits([a, b], new Map([["b", 1]]));
  expect(collapsed).toBe(1);
  const live = next.filter((row) => !row.deleted_at);
  expect(live).toHaveLength(1);
  expect(live[0]?.people).toEqual(["Petr", "Jana"]);
  expect(live[0]?.note).toBe("B · A");
  expect(live[0]?.rating).toBe(5);
  expect(photoMoves).toEqual([{ from: "a", to: "b" }]);
});

test("při stejném skóre a čase vyhraje menší id", () => {
  const a = visit("0198f93b-618d-762f-a589-ccf375139dd9");
  const b = visit("0198f93b-618d-762f-a589-ccf375139dda");
  const { next, collapsed } = collapseFamilyVisits([b, a]);
  expect(collapsed).toBe(1);
  const live = next.filter((row) => !row.deleted_at);
  expect(live).toHaveLength(1);
  expect(live[0]?.id).toBe("0198f93b-618d-762f-a589-ccf375139dd9");
});

test("jiné dny zůstanou dvě návštěvy", () => {
  const { collapsed, next } = collapseFamilyVisits([
    visit("a", { visited_at: "2026-08-09" }),
    visit("b", { visited_at: "2026-08-10" }),
  ]);
  expect(collapsed).toBe(0);
  expect(next.filter((row) => !row.deleted_at)).toHaveLength(2);
});

test("collapseFamilyVisits ořeže mezery u data jako Python", () => {
  const { collapsed, next } = collapseFamilyVisits([
    visit("a", { visited_at: "2026-08-09" }),
    visit("b", { visited_at: " 2026-08-09 " }),
  ]);
  expect(collapsed).toBe(1);
  expect(next.filter((row) => !row.deleted_at)).toHaveLength(1);
});

test("unionFamilyStates OR want/favorite a spojí poznámky", () => {
  const merged = unionFamilyStates(
    [{ place_id: "p", want_to_visit: true, favorite: false, personal_note: "A", updated_at: "t", deleted_at: null }],
    [{ place_id: "p", want_to_visit: false, favorite: true, personal_note: "B", updated_at: "t2", deleted_at: null }],
  );
  expect(merged[0]?.want_to_visit).toBe(true);
  expect(merged[0]?.favorite).toBe(true);
  expect(merged[0]?.personal_note).toBe("A · B");
});

test("reassignPhotos přepíše visit_id", () => {
  const photos = reassignPhotos(
    [{ id: "ph", visit_id: "a", mime: "image/jpeg", blob: new Blob(), created_at: "t" } satisfies StoredVisitPhoto],
    [{ from: "a", to: "b" }],
  );
  expect(photos[0]?.visit_id).toBe("b");
});

test("reassignPhotos nepřečerpá 3 fotky na návštěvu", () => {
  const photos: StoredVisitPhoto[] = [
    { id: "1", visit_id: "b", mime: "image/jpeg", blob: new Blob(), created_at: "t1" },
    { id: "2", visit_id: "b", mime: "image/jpeg", blob: new Blob(), created_at: "t2" },
    { id: "3", visit_id: "b", mime: "image/jpeg", blob: new Blob(), created_at: "t3" },
    { id: "4", visit_id: "a", mime: "image/jpeg", blob: new Blob(), created_at: "t4" },
  ];
  const next = reassignPhotos(photos, [{ from: "a", to: "b" }]);
  expect(next.map((photo) => photo.id)).toEqual(["1", "2", "3"]);
});

test("při stejném skóre a čase vyhraje menší id", () => {
  const { next } = collapseFamilyVisits([visit("b"), visit("a")]);
  const live = next.filter((row) => !row.deleted_at);
  expect(live).toHaveLength(1);
  expect(live[0]?.id).toBe("a");
});
