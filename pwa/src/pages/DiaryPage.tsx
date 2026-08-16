import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { loadPlaceSnapshots, loadPlaces } from "../catalog/importCatalog";
import type { CatalogPlace, PlaceNameSnapshot, StoredPlaceState, StoredVisit } from "../catalog/types";
import { badgesForDisplay, computeBadges } from "../diary/badges";
import { loadPlaceStates, loadVisits } from "../diary/store";
import { TripPanel } from "../components/TripPanel";
import {
  diaryHeaderStats,
  formatDiaryStatsLine,
  isDiarySection,
  listFavoriteRows,
  listVisitRows,
  listWantToVisitRows,
  type DiarySection,
} from "../diary/timeline";

function placesMap(places: CatalogPlace[]): Map<string, CatalogPlace> {
  return new Map(places.map((place) => [place.id, place]));
}

function snapshotsMap(rows: PlaceNameSnapshot[]): Map<string, PlaceNameSnapshot> {
  return new Map(rows.map((row) => [row.place_id, row]));
}

export function DiaryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const section: DiarySection = isDiarySection(searchParams.get("sec")) ? (searchParams.get("sec") as DiarySection) : "visits";
  const [visits, setVisits] = useState<StoredVisit[] | null>(null);
  const [states, setStates] = useState<StoredPlaceState[]>([]);
  const [places, setPlaces] = useState<CatalogPlace[]>([]);
  const [snapshots, setSnapshots] = useState<PlaceNameSnapshot[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const reload = async () => {
      try {
        const [visitRows, stateRows, catalog, names] = await Promise.all([
          loadVisits(),
          loadPlaceStates(),
          loadPlaces(),
          loadPlaceSnapshots(),
        ]);
        if (cancelled) {
          return;
        }
        setVisits(visitRows);
        setStates(stateRows);
        setPlaces(catalog);
        setSnapshots(names);
        setLoadError(null);
      } catch {
        if (!cancelled) {
          setLoadError("Deník se nepodařilo načíst.");
        }
      }
    };
    void reload();
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
  }, []);

  const byId = useMemo(() => placesMap(places), [places]);
  const bySnapshot = useMemo(() => snapshotsMap(snapshots), [snapshots]);
  const stats = useMemo(() => diaryHeaderStats(visits ?? [], states), [visits, states]);
  const visitRows = useMemo(() => listVisitRows(visits ?? [], byId, bySnapshot), [visits, byId, bySnapshot]);
  const wantRows = useMemo(() => listWantToVisitRows(states, byId, bySnapshot), [states, byId, bySnapshot]);
  const favRows = useMemo(() => listFavoriteRows(states, byId, bySnapshot), [states, byId, bySnapshot]);
  const badges = useMemo(() => badgesForDisplay(computeBadges(visits ?? [], places)), [visits, places]);

  const setSection = (next: DiarySection) => {
    const params = new URLSearchParams(searchParams);
    if (next === "visits") {
      params.delete("sec");
    } else {
      params.set("sec", next);
    }
    setSearchParams(params, { replace: true });
  };

  if (loadError) {
    return (
      <p className="error" role="alert">
        {loadError}
      </p>
    );
  }

  if (visits === null) {
    return <p className="muted">Načítám deník…</p>;
  }

  return (
    <section className="diary-page">
      <header className="page-header">
        <h1>Deník</h1>
        <p className="muted">{formatDiaryStatsLine(stats)}</p>
      </header>

      {badges.length > 0 ? (
        <ul className="badge-list" aria-label="Odznaky">
          {badges.map((badge) => (
            <li key={badge.id} className={badge.unlocked ? "badge unlocked" : "badge locked"}>
              <strong>{badge.title}</strong>
              <span className="muted">{badge.detail}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted small">Odznaky se objeví po první návštěvě.</p>
      )}

      <div className="segmented" role="tablist" aria-label="Části deníku">
        <button type="button" role="tab" aria-selected={section === "visits"} className={section === "visits" ? "active" : ""} onClick={() => setSection("visits")}>
          Návštěvy
        </button>
        <button type="button" role="tab" aria-selected={section === "want"} className={section === "want" ? "active" : ""} onClick={() => setSection("want")}>
          Chci navštívit
        </button>
        <button type="button" role="tab" aria-selected={section === "fav"} className={section === "fav" ? "active" : ""} onClick={() => setSection("fav")}>
          Oblíbené
        </button>
        <button type="button" role="tab" aria-selected={section === "trips"} className={section === "trips" ? "active" : ""} onClick={() => setSection("trips")}>
          Výlety
        </button>
      </div>

      {section === "visits" ? (
        visitRows.length === 0 ? (
          <p className="muted">Zatím žádná návštěva.</p>
        ) : (
          <ul className="place-list">
            {visitRows.map((row) => (
              <li key={row.visit.id}>
                <Link to={`/place/${row.place_id}?from=diary`} state={{ from: "diary" }} className="place-row">
                  <span className="place-row-title">
                    {row.dateLabel} · {row.name}
                  </span>
                  <span className="place-row-meta">
                    {row.stars}
                    {row.municipality ? ` · ${row.municipality}` : ""}
                    {row.missingFromCatalog ? " · mimo katalog" : ""}
                    {row.notePreview ? ` · ${row.notePreview}` : ""}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )
      ) : null}

      {section === "want" ? (
        wantRows.length === 0 ? (
          <p className="muted">Zatím žádné místo k návštěvě.</p>
        ) : (
          <ul className="place-list">
            {wantRows.map((row) => (
              <li key={row.place_id}>
                <Link to={`/place/${row.place_id}?from=diary`} state={{ from: "diary" }} className="place-row">
                  <span className="place-row-title">{row.name}</span>
                  <span className="place-row-meta">
                    {row.municipality ?? ""}
                    {row.missingFromCatalog ? `${row.municipality ? " · " : ""}mimo katalog` : ""}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )
      ) : null}

      {section === "fav" ? (
        favRows.length === 0 ? (
          <p className="muted">Zatím žádné oblíbené.</p>
        ) : (
          <ul className="place-list">
            {favRows.map((row) => (
              <li key={row.place_id}>
                <Link to={`/place/${row.place_id}?from=diary`} state={{ from: "diary" }} className="place-row">
                  <span className="place-row-title">{row.name}</span>
                  <span className="place-row-meta">
                    {row.municipality ?? ""}
                    {row.missingFromCatalog ? `${row.municipality ? " · " : ""}mimo katalog` : ""}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )
      ) : null}

      {section === "trips" ? <TripPanel placesById={byId} snapshotsById={bySnapshot} /> : null}

      <p className="muted small">Úpravy návštěv jsou u detailu místa. Výlet se přenáší v diary.json.</p>
    </section>
  );
}
