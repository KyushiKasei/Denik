import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { CatalogPlace } from "../catalog/types";
import { StampButton } from "./StampButton";
import { dismissProximity, loadDismissedProximityId, nearestPlaceHere, PROXIMITY_KM } from "../geo/proximity";
import { todayIsoDate } from "../diary/ids";
import { visitOnDate } from "../diary/stamp";
import type { StoredVisit } from "../catalog/types";

export function NearPlacePrompt({
  places,
  visits,
  stampedTodayIds,
  onStamped,
}: {
  places: CatalogPlace[];
  visits: StoredVisit[];
  stampedTodayIds?: Set<string>;
  onStamped: () => void;
}) {
  const [here, setHere] = useState<{ latitude: number; longitude: number } | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    if (!navigator.geolocation) {
      return;
    }
    let cancelled = false;
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        if (cancelled) {
          return;
        }
        setHere({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
      },
      () => undefined,
      { enableHighAccuracy: false, maximumAge: 15_000, timeout: 8_000 },
    );
    return () => {
      cancelled = true;
      navigator.geolocation.clearWatch(watchId);
    };
  }, []);

  if (!here || hidden) {
    return null;
  }
  const hit = nearestPlaceHere(places, here, PROXIMITY_KM);
  if (!hit) {
    return null;
  }
  if (loadDismissedProximityId() === hit.place.id) {
    return null;
  }
  const today = todayIsoDate();
  const already =
    stampedTodayIds?.has(hit.place.id) || Boolean(visitOnDate(visits.filter((row) => row.place_id === hit.place.id), today));
  if (already) {
    return null;
  }
  const meters = Math.round(hit.km * 1000);

  return (
    <section className="proximity-banner" role="status">
      <p>
        Jste u <Link to={`/place/${hit.place.id}?from=today`}>{hit.place.name}</Link>
        {` · ${meters} m`}. Orazítkovat?
      </p>
      <div className="today-actions">
        <StampButton placeId={hit.place.id} alreadyToday={false} size="compact" onStamped={onStamped} />
        <button
          type="button"
          className="ghost"
          onClick={() => {
            dismissProximity(hit.place.id);
            setHidden(true);
          }}
        >
          Teď ne
        </button>
      </div>
    </section>
  );
}
