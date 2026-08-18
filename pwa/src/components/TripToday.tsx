import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { HoursBadge } from "./HoursBadge";
import { RouteLinks } from "./RouteLinks";
import { StampButton } from "./StampButton";
import { completeTrip, tripStatusLabel } from "../diary/completeTrip";
import { dateAtNoon } from "../catalog/openingHours";
import { tripTodayProgress } from "../diary/tripToday";
import type { StoredTrip } from "../diary/types";
import { formatVisitDate } from "../diary/timeline";

export function TripToday({
  trip,
  placesById,
  visits,
  today,
  here,
  onStamped,
}: {
  trip: StoredTrip;
  placesById: Map<string, CatalogPlace>;
  visits: StoredVisit[];
  today: string;
  here: { latitude: number; longitude: number } | null;
  onStamped: () => void;
}) {
  const progress = tripTodayProgress(trip, placesById, visits, today, here);
  const when = dateAtNoon(today);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const alive = useRef(true);
  const missed = progress.stops.filter((stop) => !stop.done);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const closeTrip = async (stampMissing: boolean) => {
    if (busy) {
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const result = await completeTrip(trip, placesById, visits, today, { stampMissing });
      if (!alive.current) {
        return;
      }
      setMessage(
        stampMissing
          ? `Výlet uzavřen (${tripStatusLabel(result.status)}). Doplněno ${result.stamped} razítek.`
          : `Výlet uzavřen (${tripStatusLabel(result.status)}). ${missed.length ? `Vynecháno: ${missed.map((stop) => stop.name).join(", ")}.` : ""}`,
      );
      onStamped();
    } catch {
      if (alive.current) {
        setMessage("Výlet se nepodařilo uzavřít.");
      }
    } finally {
      if (alive.current) {
        setBusy(false);
      }
    }
  };

  if (progress.stops.length === 0) {
    return (
      <section className="today-block">
        <h2>Dnešní výlet</h2>
        <p>
          <Link to="/diary?sec=trips">{trip.name}</Link>
          {trip.planned_on ? ` · ${formatVisitDate(trip.planned_on)}` : ""} — zatím bez zastávek.
        </p>
      </section>
    );
  }

  const peopleToday = [
    ...new Set(
      visits
        .filter((visit) => !visit.deleted_at && visit.visited_at === today)
        .flatMap((visit) => visit.people),
    ),
  ];

  return (
    <section className="today-block trip-today">
      <h2>Dnešní výlet</h2>
      <p>
        <Link to={`/diary?sec=trips&trip=${trip.id}`}>{trip.name}</Link>
        {progress.airKm != null ? ` · ${progress.airKm.toFixed(0)} km vzduchem` : ""}
        {` · ${progress.doneCount}/${progress.stops.length}`}
        {trip.status ? ` · ${tripStatusLabel(trip.status)}` : ""}
      </p>
      {progress.allDone ? (
        <p className="notice" role="status">
          Všechny zastávky mají otisk.
          {peopleToday.length ? ` S vámi: ${peopleToday.join(", ")}.` : ""}
        </p>
      ) : progress.next ? (
        <div className="trip-next">
          <p>
            Další: <Link to={`/place/${progress.next.placeId}?from=today`}>{progress.next.name}</Link>
            {progress.next.kmFromHere != null ? ` · ${progress.next.kmFromHere.toFixed(1)} km` : ""}
          </p>
          {progress.next.hoursLine ? <p className="muted small">{progress.next.hoursLine}</p> : null}
          {progress.next.openState === "closed" ? (
            <p className="error" role="status">
              Dnes má zavřeno.
            </p>
          ) : null}
          {(() => {
            const nextPlace = placesById.get(progress.next.placeId);
            if (!nextPlace?.location.latitude || nextPlace.location.longitude == null) {
              return null;
            }
            return (
              <RouteLinks
                dest={{ latitude: nextPlace.location.latitude, longitude: nextPlace.location.longitude }}
                destName={nextPlace.name}
                origin={here}
                showHint={false}
              />
            );
          })()}
          <div className="trip-next-links">
            {progress.next.tickets ? (
              <a href={progress.next.tickets} target="_blank" rel="noreferrer">
                Vstupenky
              </a>
            ) : null}
            {progress.next.official ? (
              <a href={progress.next.official} target="_blank" rel="noreferrer">
                Web
              </a>
            ) : null}
          </div>
          <StampButton
            placeId={progress.next.placeId}
            alreadyToday={progress.next.stampedToday}
            tripId={trip.id}
            onStamped={onStamped}
          />
        </div>
      ) : null}
      <ol className="trip-today-stops">
        {progress.stops.map((stop, index) => (
          <li key={stop.placeId} className={stop.done ? "is-done" : stop.openState === "closed" ? "is-closed" : ""}>
            <Link to={`/place/${stop.placeId}?from=today`}>
              {index + 1}. {stop.name}
            </Link>
            {stop.place ? <HoursBadge place={stop.place} at={when} /> : null}
            {stop.stampedToday ? " · dnes" : stop.done ? " · otisk" : ""}
            {stop.kmFromHere != null && !stop.done ? ` · ${stop.kmFromHere.toFixed(1)} km` : ""}
            {!stop.done ? (
              <StampButton
                placeId={stop.placeId}
                alreadyToday={stop.stampedToday}
                size="compact"
                tripId={trip.id}
                onStamped={onStamped}
              />
            ) : null}
          </li>
        ))}
      </ol>
      {!progress.allDone && missed.length > 0 ? (
        <p className="muted small">
          {progress.doneCount} z {progress.stops.length}
          {missed.length ? ` · vynecháno: ${missed.map((stop) => stop.name).join(", ")}` : ""}
        </p>
      ) : null}
      <div className="today-actions print-only-hide">
        <button type="button" className="ghost" disabled={busy} onClick={() => void closeTrip(false)}>
          {busy ? "Uzavírám…" : "Uzavřít výlet"}
        </button>
        {missed.length > 0 ? (
          <button type="button" className="ghost" disabled={busy} onClick={() => void closeTrip(true)}>
            Uzavřít a doražit razítka
          </button>
        ) : null}
      </div>
      {message ? (
        <p className="notice" role="status">
          {message}
        </p>
      ) : null}
    </section>
  );
}
