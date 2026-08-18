import { hoursBadgeLabel, minutesUntilClose, placeOpenState, type OpenState } from "../catalog/openingHours";
import type { CatalogPlace } from "../catalog/types";

export function HoursBadge({
  place,
  at,
  state,
}: {
  place?: CatalogPlace;
  at?: Date;
  state?: OpenState;
}) {
  const when = at ?? new Date();
  const resolved = state ?? (place ? placeOpenState(place, when) : "unknown");
  const remaining =
    resolved === "open" && place?.osm_opening_hours ? minutesUntilClose(place.osm_opening_hours, when) : null;
  const label = hoursBadgeLabel(resolved, { minutesUntilClose: remaining });
  if (!label) {
    return null;
  }
  const soon = remaining != null && remaining <= 90;
  return <span className={`hours-badge is-${resolved}${soon ? " is-soon" : ""}`}>{label}</span>;
}
