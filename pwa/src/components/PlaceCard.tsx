import { useState } from "react";
import { Link } from "react-router-dom";
import {
  displayPlaceName,
  formatTypes,
  locationLine,
  conditionLabel,
} from "../catalog/labels";
import type { CatalogPlace } from "../catalog/types";
import { showConditionBadge } from "../catalog/visitWorth";
import { JournalChips } from "./JournalChips";
import { HoursBadge } from "./HoursBadge";

export function PlaceCard({
  place,
  to,
  visited = false,
  want = false,
  favorite = false,
  eyebrow,
  metaExtra,
}: {
  place: CatalogPlace;
  to: string;
  visited?: boolean;
  want?: boolean;
  favorite?: boolean;
  eyebrow?: string;
  metaExtra?: string;
}) {
  const [broken, setBroken] = useState(false);
  const photo = !broken && place.image?.thumbnail_url ? place.image.thumbnail_url : null;
  const typeLine = formatTypes(place.types, {
    omitLabels: showConditionBadge(place.condition) ? [conditionLabel(place.condition)] : [],
    hideInName: place.name,
  });
  const meta = [typeLine, locationLine(place), metaExtra].filter(Boolean).join(" · ");

  return (
    <article className="place-card">
      <Link to={to} className="place-card-link">
        <div className={photo ? "place-card-photo" : "place-card-photo is-empty"} aria-hidden={photo ? undefined : true}>
          {photo ? (
            <img src={photo} alt="" loading="lazy" onError={() => setBroken(true)} />
          ) : (
            <span>{place.name.slice(0, 1)}</span>
          )}
        </div>
        <div className="place-card-body">
          {eyebrow ? <p className="place-card-eyebrow muted small">{eyebrow}</p> : null}
          <span className="place-row-title">{displayPlaceName(place.name)}</span>
          {showConditionBadge(place.condition) ? (
            <span className="place-card-badge">{conditionLabel(place.condition)}</span>
          ) : null}
          {meta ? <span className="place-row-meta">{meta}</span> : null}
          <HoursBadge place={place} />
          <JournalChips visited={visited} want={want} favorite={favorite} />
        </div>
      </Link>
    </article>
  );
}
