import type { CatalogPlace, ConditionCode, VisitabilityCode } from "./types";

export const WORTH_VIEW_KEY = "pamatky.catalog.worth";

const HIDDEN_CONDITIONS = new Set<ConditionCode>(["EXTINCT", "REMAINS"]);
const HIDDEN_VISITABILITY = new Set<VisitabilityCode>(["EXTINCT", "CLOSED", "PRIVATE"]);
const STUB_VISITABILITY = new Set<VisitabilityCode>(["UNKNOWN", "PRIVATE"]);
const CONDITION_BADGE = new Set<ConditionCode>(["RUIN", "REMAINS", "EXTINCT"]);

export function parseWorthParam(raw: string | null | undefined): boolean | null {
  if (raw == null) {
    return null;
  }
  const text = String(raw).trim().toLowerCase();
  if (text === "all" || text === "0" || text === "false") {
    return false;
  }
  if (text === "1" || text === "visit" || text === "true") {
    return true;
  }
  return null;
}

export function loadWorthFilter(): boolean {
  try {
    const stored = localStorage.getItem(WORTH_VIEW_KEY);
    if (stored === "0") {
      return false;
    }
    if (stored === "1") {
      return true;
    }
  } catch {
    // private mode / quota
  }
  return true;
}

export function saveWorthFilter(value: boolean): void {
  try {
    localStorage.setItem(WORTH_VIEW_KEY, value ? "1" : "0");
  } catch {
    // private mode / quota
  }
}

export function hasCatalogImage(place: CatalogPlace): boolean {
  return Boolean(place.image?.thumbnail_url || place.image?.original_url);
}

export function isGone(place: CatalogPlace): boolean {
  return HIDDEN_CONDITIONS.has(place.condition) || place.visitability === "EXTINCT";
}

export function isWeakStub(place: CatalogPlace): boolean {
  if (place.condition !== "UNKNOWN") {
    return false;
  }
  if (hasCatalogImage(place) || place.links.official) {
    return false;
  }
  if (place.heritage_status === "NKP" || place.unesco) {
    return false;
  }
  return STUB_VISITABILITY.has(place.visitability);
}

export function isWorthVisiting(place: CatalogPlace): boolean {
  if (HIDDEN_CONDITIONS.has(place.condition)) {
    return false;
  }
  if (HIDDEN_VISITABILITY.has(place.visitability)) {
    return false;
  }
  if (isWeakStub(place)) {
    return false;
  }
  return true;
}

export function visitScore(place: CatalogPlace): number {
  let score = 0;
  if (place.unesco) {
    score += 25;
  }
  if (place.heritage_status === "NKP") {
    score += 20;
  } else if (place.heritage_status === "KP") {
    score += 5;
  }
  if (place.links.official) {
    score += 15;
  }
  if (place.links.wikipedia) {
    score += 10;
  }
  if (hasCatalogImage(place)) {
    score += 8;
  }
  if (place.visitability === "REGULAR") {
    score += 20;
  } else if (place.visitability === "SEASONAL") {
    score += 15;
  } else if (place.visitability === "FREE_ACCESS") {
    score += 10;
  } else if (place.visitability === "EXTERIOR_ONLY") {
    score += 5;
  } else if (place.visitability === "BY_APPOINTMENT") {
    score += 3;
  } else if (place.visitability === "EVENTS_ONLY") {
    score += 2;
  } else if (place.visitability === "PRIVATE" || place.visitability === "CLOSED") {
    score -= 50;
  } else if (place.visitability === "TEMPORARILY_CLOSED") {
    score -= 10;
  } else if (place.visitability === "EXTINCT") {
    score -= 80;
  }
  if (place.condition === "PRESERVED") {
    score += 15;
  } else if (place.condition === "REBUILT") {
    score += 12;
  } else if (place.condition === "RUIN") {
    score += 8;
  } else if (place.condition === "REMAINS") {
    score -= 25;
  } else if (place.condition === "EXTINCT") {
    score -= 80;
  }
  return score;
}

export function showConditionBadge(condition: ConditionCode): boolean {
  return CONDITION_BADGE.has(condition);
}
