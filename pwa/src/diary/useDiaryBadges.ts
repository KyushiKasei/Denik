import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import type { OrphanGroup } from "./orphans";
import { listOrphanedDiary } from "./orphans";
import { favoritePlaceIds, visitedPlaceIds, wantToVisitPlaceIds } from "./store";

export function useDiaryBadges(options?: { orphans?: boolean }) {
  const location = useLocation();
  const loadOrphans = options?.orphans === true;
  const [visitedIds, setVisitedIds] = useState<Set<string>>(new Set());
  const [wantIds, setWantIds] = useState<Set<string>>(new Set());
  const [favIds, setFavIds] = useState<Set<string>>(new Set());
  const [orphans, setOrphans] = useState<OrphanGroup[]>([]);

  const reload = useCallback(async () => {
    const [visited, want, fav, orphanGroups] = await Promise.all([
      visitedPlaceIds(),
      wantToVisitPlaceIds(),
      favoritePlaceIds(),
      loadOrphans ? listOrphanedDiary() : Promise.resolve([] as OrphanGroup[]),
    ]);
    setVisitedIds(visited);
    setWantIds(want);
    setFavIds(fav);
    if (loadOrphans) {
      setOrphans(orphanGroups);
    }
  }, [loadOrphans]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await reload();
      if (cancelled) {
        return;
      }
    })();
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        void reload();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [reload, location.pathname]);

  return { visitedIds, wantIds, favIds, orphans, reload };
}
