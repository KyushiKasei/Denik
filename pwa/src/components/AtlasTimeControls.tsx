import type { AtlasCursor, AtlasTimelineEvent } from "../diary/atlas";
import {
  atlasTimeCaption,
  atlasYears,
  lastIndexForYear,
} from "../diary/atlas";

export function AtlasTimeControls({
  timeline,
  cursor,
  playing,
  onCursor,
  onPlayToggle,
}: {
  timeline: AtlasTimelineEvent[];
  cursor: AtlasCursor;
  playing: boolean;
  onCursor: (cursor: AtlasCursor) => void;
  onPlayToggle: () => void;
}) {
  if (timeline.length === 0) {
    return null;
  }
  const years = atlasYears(timeline);
  const last = timeline.length - 1;
  const sliderValue = cursor === "today" ? last : Math.max(0, cursor);
  const currentYear =
    cursor === "today" || cursor < 0 ? null : Number(timeline[cursor]?.visitedAt?.slice(0, 4) || 0) || null;

  return (
    <div className="atlas-time">
      <p className="atlas-time-caption" role="status">
        {atlasTimeCaption(timeline, cursor)}
      </p>
      {years.length > 0 ? (
        <div className="atlas-time-years" role="group" aria-label="Rok">
          {years.map((year) => (
            <button
              key={year}
              type="button"
              className={currentYear === year ? "active" : undefined}
              onClick={() => onCursor(lastIndexForYear(timeline, year))}
            >
              {year}
            </button>
          ))}
        </div>
      ) : null}
      <label className="atlas-time-slider">
        <span className="visually-hidden">Návštěvy v čase</span>
        <input
          type="range"
          min={0}
          max={last}
          step={1}
          value={sliderValue}
          aria-valuetext={atlasTimeCaption(timeline, cursor)}
          onChange={(event) => onCursor(Number(event.target.value))}
        />
      </label>
      <div className="actions-row">
        <button
          type="button"
          className="ghost"
          disabled={cursor !== "today" && cursor <= 0}
          onClick={() => {
            if (cursor === "today") {
              onCursor(last);
              return;
            }
            if (typeof cursor === "number" && cursor > 0) {
              onCursor(cursor - 1);
            }
          }}
        >
          Předchozí otisk
        </button>
        <button
          type="button"
          className="ghost"
          disabled={cursor === "today"}
          onClick={() => {
            if (typeof cursor === "number" && cursor < last) {
              onCursor(cursor + 1);
              return;
            }
            onCursor("today");
          }}
        >
          Další otisk
        </button>
        <button type="button" className={playing ? "active" : undefined} onClick={onPlayToggle}>
          {playing ? "Pauza" : "Přehrát"}
        </button>
        <button type="button" className="ghost" disabled={cursor === "today"} onClick={() => onCursor("today")}>
          Dnes
        </button>
      </div>
    </div>
  );
}
