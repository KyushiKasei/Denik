import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { loadPlaces } from "../catalog/importCatalog";
import { CzechRegionsMap } from "../components/CzechRegionsMap";
import { StampMark } from "../components/StampMark";
import { favoritePlaceIds, loadTrips, loadVisits } from "../diary/store";
import { passportPages } from "../diary/passport";
import { regionProgress } from "../diary/regions";
import { currentYear, yearbookFor } from "../diary/yearbook";
import { formatVisitDate, czechCountWord } from "../diary/timeline";

export function YearbookPage() {
  const year = currentYear();
  const [loadError, setLoadError] = useState<string | null>(null);
  const [stats, setStats] = useState<ReturnType<typeof yearbookFor> | null>(null);
  const [regions, setRegions] = useState<ReturnType<typeof regionProgress>>([]);
  const [pages, setPages] = useState<ReturnType<typeof passportPages>>([]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [places, visits, trips, fav] = await Promise.all([
          loadPlaces(),
          loadVisits(),
          loadTrips(),
          favoritePlaceIds(),
        ]);
        if (cancelled) {
          return;
        }
        setStats(yearbookFor(year, visits, places, trips, fav));
        setRegions(regionProgress(places, visits));
        setPages(passportPages(places, visits));
      } catch {
        if (!cancelled) {
          setLoadError("Ročenku se nepodařilo sestavit.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [year]);

  const stamps = useMemo(() => pages.flatMap((page) => page.stamps).slice(0, 24), [pages]);

  if (loadError) {
    return (
      <p className="error" role="alert">
        {loadError}
      </p>
    );
  }
  if (!stats) {
    return <p className="muted">Sestavuji ročenku…</p>;
  }

  return (
    <article className="yearbook">
      <header className="page-header">
        <h1>Můj rok {stats.year}</h1>
        <p className="muted">
          {stats.uniquePlaces} {czechCountWord(stats.uniquePlaces, "místo", "místa", "míst")} · {stats.visitCount}{" "}
          {czechCountWord(stats.visitCount, "návštěva", "návštěvy", "návštěv")}
          {stats.tripCount ? ` · ${stats.tripCount} výletů` : ""}
        </p>
      </header>

      <p className="print-only-hide">
        <button type="button" className="ghost" onClick={() => window.print()}>
          Tisk / PDF
        </button>
        {" · "}
        <Link to={`/map?view=atlas&until=${year}-12-31`}>Atlas tohoto roku</Link>
        {" · "}
        <Link to="/diary?sec=passport">Zpět do pasu</Link>
      </p>

      <CzechRegionsMap rows={regions} />

      {stamps.length > 0 ? (
        <ul className="yearbook-stamps">
          {stamps.map((stamp) => (
            <li key={stamp.visitId}>
              <StampMark kind={stamp.kind} wax={stamp.wax} size={56} />
              <span>{stamp.name}</span>
              <span className="muted small">{formatVisitDate(stamp.visitedAt)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Letos zatím žádný otisk.</p>
      )}

      {stats.topRated.length > 0 ? (
        <section>
          <h2>Nejlépe hodnocené</h2>
          <ol>
            {stats.topRated.map((row) => (
              <li key={row.placeId}>
                {row.name} · {"★".repeat(row.rating)}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {stats.people.length > 0 ? (
        <p className="muted">S vámi: {stats.people.join(", ")}</p>
      ) : null}
    </article>
  );
}
