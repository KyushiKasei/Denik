import type { StoredVisit } from "../catalog/types";

export interface VisitFollowUp {
  visit: StoredVisit;
  missingPhoto: boolean;
  missingNote: boolean;
}

export function visitsNeedingFollowUp(
  visits: StoredVisit[],
  photoCounts: ReadonlyMap<string, number>,
): VisitFollowUp[] {
  const rows: VisitFollowUp[] = [];
  for (const visit of visits) {
    if (visit.deleted_at) {
      continue;
    }
    const missingPhoto = (photoCounts.get(visit.id) ?? 0) === 0;
    const missingNote = !(visit.note || "").trim();
    if (!missingPhoto && !missingNote) {
      continue;
    }
    rows.push({ visit, missingPhoto, missingNote });
  }
  return rows;
}
