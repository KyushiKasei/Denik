import { useNavigate } from "react-router-dom";
import { unlockedRegionCount, type RegionProgress } from "../diary/regions";

export function CzechRegionsMap({ rows }: { rows: RegionProgress[] }) {
  const navigate = useNavigate();
  const unlocked = unlockedRegionCount(rows);

  return (
    <section className="regions-map" id="kraje" aria-label="Kraje Česka">
      <header className="regions-map-header">
        <h2>Kraje</h2>
        <p className="muted">
          {unlocked} z {rows.length} krajů s návštěvou
        </p>
      </header>
      <svg viewBox="0 0 1000 580" className="regions-svg" role="group" aria-label="Schematická mapa krajů">
        {rows.map((row) => (
          <path
            key={row.region.id}
            d={row.region.path}
            className={`region-path${row.unlocked ? " is-unlocked" : ""}${row.visited > 1 ? " is-rich" : ""}`}
            tabIndex={0}
            role="link"
            aria-label={`${row.region.name}: ${row.visited} z ${row.total}`}
            onClick={() => navigate(`/diary?sec=passport&region=${row.region.id}`)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                navigate(`/diary?sec=passport&region=${row.region.id}`);
              }
            }}
          >
            <title>
              {row.region.name}: {row.visited}
              {row.total ? ` / ${row.total}` : ""}
            </title>
          </path>
        ))}
      </svg>
      <ul className="region-legend">
        {rows
          .filter((row) => row.unlocked)
          .map((row) => (
            <li key={row.region.id}>
              <button
                type="button"
                className="text-link"
                onClick={() => navigate(`/diary?sec=passport&region=${row.region.id}`)}
              >
                {row.region.short}
              </button>
              <span className="muted">
                {" "}
                {row.visited}
                {row.total ? `/${row.total}` : ""}
              </span>
            </li>
          ))}
      </ul>
    </section>
  );
}
