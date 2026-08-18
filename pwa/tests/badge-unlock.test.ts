import { expect, test } from "vitest";
import { newlyUnlockedBadges, saveSeenBadgeIds, loadSeenBadgeIds } from "../src/diary/badgeUnlock";
import type { DiaryBadge } from "../src/diary/badges";

test("nově odemčené odznaky", () => {
  saveSeenBadgeIds(["first_visit"]);
  const badges: DiaryBadge[] = [
    { id: "first_visit", title: "První", detail: "", unlocked: true },
    { id: "places_5", title: "5", detail: "", unlocked: true },
    { id: "unesco", title: "UNESCO", detail: "", unlocked: false },
  ];
  expect(newlyUnlockedBadges(badges, loadSeenBadgeIds()).map((badge) => badge.id)).toEqual(["places_5"]);
});
