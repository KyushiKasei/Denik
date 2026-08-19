import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { loadPlaceSnapshots, loadPlaces, peekPlaces } from "../catalog/importCatalog";
import type { CatalogPlace, PlaceNameSnapshot, StoredPlaceState, StoredVisit } from "../catalog/types";
import { badgesForDisplay, computeBadges } from "../diary/badges";
import { passportPages } from "../diary/passport";
import { loadPlaceStates, loadVisits } from "../diary/store";
import { loadAllPhotos } from "../diary/photos";
import { uniquePeopleNames, visitHasPerson } from "../diary/people";
import { visitsNeedingFollowUp } from "../diary/inbox";
import { PhotoIntake } from "../components/PhotoIntake";
import { PassportAlbum } from "../components/PassportAlbum";
import { TripPanel } from "../components/TripPanel";
import { GpxTrack } from "../components/GpxTrack";
import {
  czechCountWord,
  diaryHeaderStats,
  formatDiaryStatsLine,
  isDiarySection,
  listFavoriteRows,
  listVisitRows,
  listWantToVisitRows,
  municipalityLine,
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
  const section: DiarySection = isDiarySection(searchParams.get("sec"))
    ? (searchParams.get("sec") as DiarySection)
    : "passport";
  const [visits, setVisits] = useState<StoredVisit[] | null>(null);
  const [states, setStates] = useState<StoredPlaceState[]>([]);
  const [places, setPlaces] = useState<CatalogPlace[]>(() => peekPlaces() ?? []);
  const [snapshots, setSnapshots] = useState<PlaceNameSnapshot[]>([]);
  const [photoCounts, setPhotoCounts] = useState<Map<string, number>>(new Map());
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const who = searchParams.get("who") ?? "";
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    let cancelled = false;
    const reload = async () => {
      try {
        const [visitRows, stateRows, catalog, names, photos] = await Promise.all([
          loadVisits(),
          loadPlaceStates(),
          loadPlaces(),
          loadPlaceSnapshots(),
          loadAllPhotos(),
        ]);
        if (cancelled) {
          return;
        }
        setVisits(visitRows);
        setStates(stateRows);
        setPlaces(catalog);
        setSnapshots(names);
        const counts = new Map<string, number>();
        for (const photo of photos) {
          counts.set(photo.visit_id, (counts.get(photo.visit_id) ?? 0) + 1);
        }
        setPhotoCounts(counts);
        setLoadError(null);
        setRefreshError(null);
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
      alive.current = false;
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, []);

  const byId = useMemo(() => placesMap(places), [places]);
  const bySnapshot = useMemo(() => snapshotsMap(snapshots), [snapshots]);
  const stats = useMemo(() => diaryHeaderStats(visits ?? [], states), [visits, states]);
  const visitRows = useMemo(() => listVisitRows(visits ?? [], byId, bySnapshot), [visits, byId, bySnapshot]);
  const peopleNames = useMemo(() => uniquePeopleNames(visits ?? []), [visits]);
  const filteredVisitRows = useMemo(
    () => (who ? visitRows.filter((row) => visitHasPerson(row.visit, who)) : visitRows),
    [visitRows, who],
  );
  const inbox = useMemo(() => visitsNeedingFollowUp(visits ?? [], photoCounts), [visits, photoCounts]);
  const wantRows = useMemo(() => listWantToVisitRows(states, byId, bySnapshot), [states, byId, bySnapshot]);
  const favRows = useMemo(() => listFavoriteRows(states, byId, bySnapshot), [states, byId, bySnapshot]);
  const badges = useMemo(() => badgesForDisplay(computeBadges(visits ?? [], places)), [visits, places]);
  const pages = useMemo(() => passportPages(places, visits ?? [], bySnapshot), [places, visits, bySnapshot]);
  const regionId = searchParams.get("region");

  const setSection = (next: DiarySection) => {
    const params = new URLSearchParams(searchParams);
    if (next === "passport") {
      params.delete("sec");
    } else {
      params.set("sec", next);
    }
    if (next !== "passport") {
      params.delete("region");
    }
    if (next !== "trips") {
      params.delete("trip");
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
      {refreshError ? (
        <p className="error" role="alert">
          {refreshError}
        </p>
      ) : null}

      {badges.length > 0 ? (
        <ul className="badge-list" aria-label="Odznaky">
          {badges.map((badge) => (
            <li key={badge.id} className={badge.unlocked ? "badge unlocked" : "badge locked"}>
              {badge.id === "regions" ? (
                <Link to="/#kraje">
                  <strong>{badge.title}</strong>
                  <span className="muted">{badge.detail}</span>
                </Link>
              ) : (
                <>
                  <strong>{badge.title}</strong>
                  <span className="muted">{badge.detail}</span>
                </>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted small">Odznaky se objeví po první návštěvě.</p>
      )}

      <div className="segmented cols-5" role="tablist" aria-label="Části deníku">
        <button type="button" role="tab" aria-selected={section === "passport"} className={section === "passport" ? "active" : ""} onClick={() => setSection("passport")}>
          Pas
        </button>
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

      {section === "passport" ? (
        <PassportAlbum
          pages={pages}
          regionId={regionId}
          onSelectRegion={(id) => {
            const params = new URLSearchParams(searchParams);
            params.delete("sec");
            params.set("region", id);
            setSearchParams(params, { replace: true });
          }}
        />
      ) : null}

      {section === "visits" ? (
        visitRows.length === 0 ? (
          <p className="muted">Zatím žádná návštěva.</p>
        ) : (
          <>
            {inbox.length > 0 ? (
              <section className="diary-inbox">
                <h2>Doplnit</h2>
                <p className="muted small">
                  {inbox.length} {czechCountWord(inbox.length, "návštěva", "návštěvy", "návštěv")} bez fotky
                  nebo poznámky.
                </p>
                <ul className="place-list">
                  {inbox.slice(0, 8).map((row) => {
                    const place = byId.get(row.visit.place_id);
                    return (
                      <li key={row.visit.id}>
                        <Link to={`/place/${row.visit.place_id}?from=diary`} className="place-row">
                          <span className="place-row-title">{place?.name ?? "Místo"}</span>
                          <span className="place-row-meta">
                            {row.missingPhoto ? "chybí foto" : ""}
                            {row.missingPhoto && row.missingNote ? " · " : ""}
                            {row.missingNote ? "chybí poznámka" : ""}
                          </span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ) : null}
            <PhotoIntake places={places} />
            <GpxTrack
              places={places}
              visits={visits ?? []}
              onStamped={() => {
                void loadVisits()
                  .then((rows) => {
                    if (!alive.current) {
                      return;
                    }
                    setVisits(rows);
                    setRefreshError(null);
                  })
                  .catch(() => {
                    if (alive.current) {
                      setRefreshError("Deník se nepodařilo obnovit.");
                    }
                  });
              }}
            />
            {peopleNames.length > 0 ? (
              <label>
                S kým
                <select
                  value={who}
                  onChange={(event) => {
                    const params = new URLSearchParams(searchParams);
                    if (event.target.value) {
                      params.set("who", event.target.value);
                    } else {
                      params.delete("who");
                    }
                    setSearchParams(params, { replace: true });
                  }}
                >
                  <option value="">Kdokoli</option>
                  {peopleNames.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <ul className="place-list">
              {filteredVisitRows.map((row) => (
                <li key={row.visit.id}>
                  <Link to={`/place/${row.place_id}?from=diary`} state={{ from: "diary" }} className="place-row">
                    <span className="place-row-title">
                      {row.dateLabel} · {row.name}
                    </span>
                    <span className="place-row-meta">
                      {row.stars !== "—" ? row.stars : ""}
                      {municipalityLine(row.name, row.municipality)
                        ? `${row.stars !== "—" ? " · " : ""}${municipalityLine(row.name, row.municipality)}`
                        : ""}
                      {row.visit.people.length ? ` · ${row.visit.people.join(", ")}` : ""}
                      {row.missingFromCatalog ? " · mimo katalog" : ""}
                      {row.notePreview ? ` · ${row.notePreview}` : ""}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </>
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
                    {municipalityLine(row.name, row.municipality)}
                    {row.missingFromCatalog
                      ? `${municipalityLine(row.name, row.municipality) ? " · " : ""}mimo katalog`
                      : ""}
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
                    {municipalityLine(row.name, row.municipality)}
                    {row.missingFromCatalog
                      ? `${municipalityLine(row.name, row.municipality) ? " · " : ""}mimo katalog`
                      : ""}
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
