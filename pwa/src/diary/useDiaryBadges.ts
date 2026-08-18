import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import type { StoredVisit } from "../catalog/types";
import type { OrphanGroup } from "./orphans";
import { listOrphanedDiary } from "./orphans";
import { favoritePlaceIds, loadVisits, visitedPlaceIds, wantToVisitPlaceIds } from "./store";
import { todayIsoDate } from "./ids";

export function useDiaryBadges(options?: { orphans?: boolean }) {
  const location = useLocation();
  const loadOrphans = options?.orphans === true;
  const [visitedIds, setVisitedIds] = useState<Set<string>>(new Set());
  const [wantIds, setWantIds] = useState<Set<string>>(new Set());
  const [favIds, setFavIds] = useState<Set<string>>(new Set());
  const [todayIds, setTodayIds] = useState<Set<string>>(new Set());
  const [visits, setVisits] = useState<StoredVisit[]>([]);
  const [orphans, setOrphans] = useState<OrphanGroup[]>([]);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);

  const reload = useCallback(async () => {
    try {
      const today = todayIsoDate();
      const [visited, want, fav, visitRows, orphanGroups] = await Promise.all([
        visitedPlaceIds(),
        wantToVisitPlaceIds(),
        favoritePlaceIds(),
        loadVisits(),
        loadOrphans ? listOrphanedDiary() : Promise.resolve([] as OrphanGroup[]),
      ]);
      if (!alive.current) {
        return;
      }
      setVisitedIds(visited);
      setWantIds(want);
      setFavIds(fav);
      setVisits(visitRows);
      setTodayIds(new Set(visitRows.filter((visit) => visit.visited_at === today).map((visit) => visit.place_id)));
      if (loadOrphans) {
        setOrphans(orphanGroups);
      }
      setError(null);
    } catch {
      if (alive.current) {
        setError("Stav deníku se nepodařilo načíst.");
      }
    }
  }, [loadOrphans]);

  useEffect(() => {
    alive.current = true;
    void reload();
    const onVisible = () => {
      if (!alive.current) {
        return;
      }
      if (document.visibilityState === "visible") {
        void reload();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      alive.current = false;
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [reload, location.pathname]);

  return { visitedIds, wantIds, favIds, todayIds, visits, orphans, error, reload };
}
