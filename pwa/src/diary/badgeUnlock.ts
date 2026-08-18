import type { DiaryBadge } from "./badges";

export const SEEN_BADGES_KEY = "pamatky.badges.seen";

function storage(): Storage | null {
  try {
    if (typeof localStorage === "undefined") {
      return null;
    }
    return localStorage;
  } catch {
    return null;
  }
}

export function loadSeenBadgeIds(): Set<string> {
  const raw = storage()?.getItem(SEEN_BADGES_KEY);
  if (!raw) {
    return new Set();
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return new Set();
    }
    return new Set(parsed.filter((item): item is string => typeof item === "string"));
  } catch {
    return new Set();
  }
}

export function saveSeenBadgeIds(ids: Iterable<string>): void {
  storage()?.setItem(SEEN_BADGES_KEY, JSON.stringify([...ids]));
}

export function newlyUnlockedBadges(badges: DiaryBadge[], seen: Set<string>): DiaryBadge[] {
  return badges.filter((badge) => badge.unlocked && !seen.has(badge.id));
}

export function markBadgesSeen(badges: DiaryBadge[]): Set<string> {
  const next = new Set(loadSeenBadgeIds());
  for (const badge of badges) {
    if (badge.unlocked) {
      next.add(badge.id);
    }
  }
  saveSeenBadgeIds(next);
  return next;
}
