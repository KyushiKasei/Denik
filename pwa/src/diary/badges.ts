import type { CatalogPlace, PlaceTypeCode, StoredVisit } from "../catalog/types";
import { typeLabel } from "../catalog/labels";
import { uniqueVisitedPlaceIds } from "./timeline";

export interface DiaryBadge {
  id: string;
  title: string;
  detail: string;
  unlocked: boolean;
}

const PLACE_MILESTONES = [5, 10, 25, 50] as const;

const FIRST_TYPE_ORDER: PlaceTypeCode[] = [
  "CASTLE",
  "CHATEAU",
  "RUIN",
  "FORTRESS",
  "MANOR",
  "PALACE",
  "LOOKOUT_TOWER",
  "ZOO",
  "CAVE",
];

function activeVisits(visits: StoredVisit[]): StoredVisit[] {
  return visits.filter((visit) => !visit.deleted_at);
}

function czechPlacesWord(count: number): string {
  if (count === 1) {
    return "místo";
  }
  if (count >= 2 && count <= 4) {
    return "místa";
  }
  return "míst";
}

function czechKrajeWord(count: number): string {
  if (count === 1) {
    return "kraj";
  }
  if (count >= 2 && count <= 4) {
    return "kraje";
  }
  return "krajů";
}

export function computeBadges(visits: StoredVisit[], places: CatalogPlace[]): DiaryBadge[] {
  const live = activeVisits(visits);
  const uniqueIds = uniqueVisitedPlaceIds(live);
  const uniqueCount = uniqueIds.size;
  const placesById = new Map(places.map((place) => [place.id, place]));

  const visitedPlaces = [...uniqueIds]
    .map((id) => placesById.get(id))
    .filter((place): place is CatalogPlace => Boolean(place));

  const visitedTypes = new Set(visitedPlaces.flatMap((place) => place.types));
  const visitedUnesco = visitedPlaces.some((place) => place.unesco);
  const regions = new Set(
    visitedPlaces.map((place) => place.location.region?.trim()).filter((region): region is string => Boolean(region)),
  );

  const badges: DiaryBadge[] = [];

  badges.push({
    id: "first_visit",
    title: "První návštěva",
    detail: uniqueCount > 0 ? "V deníku je alespoň jedna návštěva." : "Zapište první návštěvu u místa.",
    unlocked: uniqueCount > 0,
  });

  for (const n of PLACE_MILESTONES) {
    badges.push({
      id: `places_${n}`,
      title: `${n} navštívených míst`,
      detail:
        uniqueCount >= n
          ? `Navštíveno ${n} ${czechPlacesWord(n)}.`
          : `Zatím ${uniqueCount} ${czechPlacesWord(uniqueCount)}.`,
      unlocked: uniqueCount >= n,
    });
  }

  badges.push({
    id: "unesco",
    title: "Návštěva UNESCO",
    detail: visitedUnesco ? "V deníku je místo ze seznamu UNESCO." : "Zatím bez navštíveného UNESCO.",
    unlocked: visitedUnesco,
  });

  if (regions.size > 0) {
    badges.push({
      id: "regions",
      title: `Navštíveno ${regions.size} ${czechKrajeWord(regions.size)}`,
      detail: [...regions].sort((a, b) => a.localeCompare(b, "cs")).join(", "),
      unlocked: true,
    });
  }

  const firstTypeTitle: Record<PlaceTypeCode, string> = {
    CASTLE: "První hrad",
    CHATEAU: "První zámek",
    RUIN: "První zřícenina",
    FORTRESS: "První pevnost",
    MANOR: "První tvrz",
    PALACE: "První palác",
    LOOKOUT_TOWER: "První rozhledna",
    ZOO: "První zoo",
    CAVE: "První jeskyně",
    OTHER: "První jiné",
  };

  for (const type of FIRST_TYPE_ORDER) {
    const unlocked = visitedTypes.has(type);
    badges.push({
      id: `first_${type.toLowerCase()}`,
      title: firstTypeTitle[type],
      detail: unlocked ? `V deníku je návštěva: ${typeLabel(type)}.` : `Zatím bez typu ${typeLabel(type)}.`,
      unlocked,
    });
  }

  return badges;
}

export function badgesForDisplay(badges: DiaryBadge[]): DiaryBadge[] {
  const unlocked = badges.filter((badge) => badge.unlocked);
  if (unlocked.length === 0) {
    return [];
  }
  const nextMilestone = badges.find((badge) => badge.id.startsWith("places_") && !badge.unlocked);
  if (nextMilestone && !unlocked.some((badge) => badge.id === nextMilestone.id)) {
    return [...unlocked, nextMilestone];
  }
  return unlocked;
}
