import { Link } from "react-router-dom";
import { czechCountWord } from "../diary/timeline";
import type { OrphanGroup } from "../diary/orphans";

function visitSummary(group: OrphanGroup): string {
  const parts: string[] = [];
  if (group.visits.length > 0) {
    parts.push(`${group.visits.length} ${czechCountWord(group.visits.length, "návštěva", "návštěvy", "návštěv")}`);
  }
  if (group.state?.want_to_visit) {
    parts.push("chci navštívit");
  }
  if (group.state?.favorite) {
    parts.push("oblíbené");
  }
  return parts.join(" · ") || "záznam v deníku";
}

function title(group: OrphanGroup): string {
  return group.last_name?.trim() || "Místo už není v katalogu";
}

export function OrphanVisits({ groups }: { groups: OrphanGroup[] }) {
  if (groups.length === 0) {
    return null;
  }
  return (
    <section className="orphan-panel" aria-label="Osiřelé návštěvy">
      <h2>Místo už není v katalogu</h2>
      <p className="muted">
        Deník se nesmazal. Tato místa v aktuálním <code>catalog.json</code> chybí (archiv na PC nebo starší export).
      </p>
      <ul className="place-list">
        {groups.map((group) => (
          <li key={group.place_id}>
            <Link to={`/place/${group.place_id}`} className="place-row">
              <span className="place-row-title">{title(group)}</span>
              <span className="place-row-meta">
                {visitSummary(group)}
                {group.last_municipality ? ` · ${group.last_municipality}` : ""}
                {" · "}
                <code>{group.place_id}</code>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
