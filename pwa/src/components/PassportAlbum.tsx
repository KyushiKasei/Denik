import { Link } from "react-router-dom";
import type { PassportPage } from "../diary/passport";
import { formatVisitDate } from "../diary/timeline";
import { StampMark } from "./StampMark";

export function PassportAlbum({
  pages,
  regionId,
  onSelectRegion,
}: {
  pages: PassportPage[];
  regionId: string | null;
  onSelectRegion: (id: string) => void;
}) {
  const selected = pages.find((page) => page.region.id === regionId) ?? pages.find((page) => page.stamps.length > 0) ?? pages[0];
  if (!selected) {
    return <p className="muted">Pas se vyplní po prvním razítku.</p>;
  }

  return (
    <section className="passport-album">
      <div className="passport-tabs" role="tablist" aria-label="Stránky krajů">
        {pages.map((page) => (
          <button
            key={page.region.id}
            type="button"
            role="tab"
            aria-selected={page.region.id === selected.region.id}
            className={page.region.id === selected.region.id ? "active" : ""}
            onClick={() => onSelectRegion(page.region.id)}
          >
            {page.region.short}
            {page.stamps.length ? ` ${page.stamps.length}` : ""}
          </button>
        ))}
      </div>
      <header className="passport-page-header">
        <h2>{selected.region.name}</h2>
        <p className="muted">
          {selected.stamps.length}
          {selected.total ? `/${selected.total}` : ""} míst
        </p>
      </header>
      <ul className="passport-grid">
        {selected.stamps.map((stamp) => (
          <li key={stamp.visitId}>
            <Link to={`/place/${stamp.placeId}?from=diary`} state={{ from: "diary" }} className="passport-stamp">
              <StampMark kind={stamp.kind} wax={stamp.wax} size={72} />
              <span className="passport-stamp-name">{stamp.name}</span>
              <span className="muted small">{formatVisitDate(stamp.visitedAt)}</span>
            </Link>
          </li>
        ))}
        {Array.from({ length: selected.emptySlots }, (_, index) => (
          <li key={`empty-${index}`} className="passport-stamp is-empty" aria-hidden>
            <StampMark kind="other" wax="currentColor" size={72} empty />
          </li>
        ))}
      </ul>
      {selected.stamps.length === 0 ? <p className="muted">V tomto kraji zatím žádné razítko.</p> : null}
      <p className="muted small">
        <Link to={`/map?view=atlas&region=${encodeURIComponent(selected.region.name)}`}>Atlas tohoto kraje</Link>
        {" · "}
        <Link to="/yearbook">Ročenka k tisku</Link>
      </p>
    </section>
  );
}
