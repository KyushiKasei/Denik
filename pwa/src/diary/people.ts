import type { StoredVisit } from "../catalog/types";

export function uniquePeopleNames(visits: StoredVisit[]): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const visit of visits) {
    if (visit.deleted_at) {
      continue;
    }
    for (const name of visit.people) {
      const trimmed = name.trim();
      if (!trimmed || seen.has(trimmed)) {
        continue;
      }
      seen.add(trimmed);
      names.push(trimmed);
    }
  }
  return names.sort((a, b) => a.localeCompare(b, "cs"));
}

export function visitHasPerson(visit: StoredVisit, who: string): boolean {
  const needle = who.trim().toLocaleLowerCase("cs");
  if (!needle) {
    return true;
  }
  return visit.people.some((name) => name.trim().toLocaleLowerCase("cs") === needle);
}
