import { useEffect, useMemo, useRef, useState } from "react";
import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { readPhotoExif } from "../diary/exif";
import { todayIsoDate } from "../diary/ids";
import {
  applyPhotoMatch,
  defaultPhotoVisitChoice,
  liveVisitsForPlace,
  PHOTO_MATCH_MAX_KM,
  PHOTO_SUGGEST_MAX_KM,
  suggestPhotoMatches,
  type PhotoPlaceMatch,
  type PhotoVisitChoice,
} from "../diary/photoMatch";
import { loadVisits } from "../diary/store";
import { czechCountWord, formatVisitDate } from "../diary/timeline";
import { fold } from "../text/fold";

const MAX_INTAKE_BYTES = 20 * 1024 * 1024;
const MAX_INTAKE_FILES = 40;
const SEARCH_LIMIT = 8;

function metersLabel(km: number): string {
  return km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1).replace(".", ",")} km`;
}

function searchPlaces(places: CatalogPlace[], query: string): CatalogPlace[] {
  const needle = fold(query.trim());
  if (needle.length < 3) {
    return [];
  }
  const hits: CatalogPlace[] = [];
  for (const place of places) {
    const hay = fold(
      [place.name, place.short_name ?? "", place.location.municipality ?? "", ...place.alternative_names].join(" "),
    );
    if (hay.includes(needle)) {
      hits.push(place);
      if (hits.length >= SEARCH_LIMIT) {
        break;
      }
    }
  }
  return hits;
}

function visitOptionLabel(visit: StoredVisit, today: string, exifDay: string): string {
  const day = (visit.visited_at || "").trim();
  const date = formatVisitDate(visit.visited_at);
  const tags: string[] = [];
  if (day === today) {
    tags.push("dnes");
  }
  if (day === exifDay && exifDay !== today) {
    tags.push("datum z fotky");
  }
  return tags.length ? `${date} · ${tags.join(", ")}` : date;
}

function rowStatus(row: PhotoPlaceMatch): string {
  const date = formatVisitDate(row.visitedAt);
  if (row.place && row.km != null && row.km <= PHOTO_MATCH_MAX_KM) {
    return `${row.place.name} · ${metersLabel(row.km)} · fotka ${date}`;
  }
  if (row.place && row.km != null) {
    return `návrh: ${row.place.name} · ${metersLabel(row.km)} · fotka ${date}`;
  }
  if (row.place) {
    return `${row.place.name} · fotka ${date}`;
  }
  if (row.exif.latitude != null && row.exif.longitude != null) {
    return `GPS je, ale místo do ${PHOTO_SUGGEST_MAX_KM} km chybí · ${date}`;
  }
  return `bez GPS v EXIF · vyberte místo · ${date}`;
}

export function PhotoIntake({
  places,
  initialFiles,
}: {
  places: CatalogPlace[];
  initialFiles?: File[];
}) {
  const [rows, setRows] = useState<PhotoPlaceMatch[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [queries, setQueries] = useState<Record<number, string>>({});
  const [choices, setChoices] = useState<Record<number, PhotoVisitChoice>>({});
  const [visits, setVisits] = useState<StoredVisit[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const alive = useRef(true);
  const shareKey = (initialFiles ?? []).map((file) => `${file.name}:${file.size}`).join("|");
  const today = todayIsoDate();

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const refreshVisits = async () => {
    const next = await loadVisits();
    if (alive.current) {
      setVisits(next);
    }
    return next;
  };

  useEffect(() => {
    void refreshVisits().catch(() => {
      if (alive.current) {
        setError("Návštěvy se nepodařilo načíst.");
      }
    });
  }, []);

  const choiceFor = (row: PhotoPlaceMatch, place: CatalogPlace, currentVisits = visits): PhotoVisitChoice =>
    defaultPhotoVisitChoice(currentVisits, place.id, row.visitedAt, today);

  const processFiles = async (files: File[]) => {
    if (files.length === 0 || busy) {
      return;
    }
    const oversized = files.filter((file) => file.size > MAX_INTAKE_BYTES);
    const withinSize = files.filter((file) => file.size <= MAX_INTAKE_BYTES);
    const usable = withinSize.slice(0, MAX_INTAKE_FILES);
    const messages: string[] = [];
    if (oversized.length) {
      messages.push("Některé fotky jsou větší než 20 MB a přeskočily se.");
    }
    if (withinSize.length > MAX_INTAKE_FILES) {
      messages.push(`Najednou jde zpracovat nejvýš ${MAX_INTAKE_FILES} fotek.`);
    }
    setError(messages.join(" ") || null);
    setDone(null);
    if (usable.length === 0) {
      return;
    }
    setBusy(true);
    try {
      const [exifs, latestVisits] = await Promise.all([
        Promise.all(usable.map((file) => readPhotoExif(file))),
        refreshVisits(),
      ]);
      if (!alive.current) {
        return;
      }
      const next = suggestPhotoMatches(usable, places, exifs);
      setRows(next);
      setQueries({});
      setChoices(
        Object.fromEntries(
          next.flatMap((row, index) => (row.place ? [[index, choiceFor(row, row.place, latestVisits)]] : [])),
        ),
      );
      setSelected(new Set(next.map((row, index) => (row.confident ? index : -1)).filter((index) => index >= 0)));
    } catch (err) {
      if (alive.current) {
        setError(err instanceof Error ? err.message : "Fotky se nepodařilo přečíst.");
      }
    } finally {
      if (alive.current) {
        setBusy(false);
      }
    }
  };

  useEffect(() => {
    if (!initialFiles?.length) {
      return;
    }
    void processFiles(initialFiles);
  }, [shareKey, places.length]);

  const onFiles = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) {
      return;
    }
    await processFiles([...fileList]);
  };

  const assignPlace = (index: number, place: CatalogPlace, km: number | null) => {
    setRows((current) =>
      current.map((row, rowIndex) =>
        rowIndex === index
          ? {
              ...row,
              place,
              km,
              confident: km != null && km <= PHOTO_MATCH_MAX_KM,
            }
          : row,
      ),
    );
    setSelected((current) => {
      const next = new Set(current);
      next.add(index);
      return next;
    });
    setQueries((current) => ({ ...current, [index]: "" }));
    setChoices((current) => {
      const row = rows[index];
      if (!row) {
        return current;
      }
      return { ...current, [index]: choiceFor({ ...row, place }, place) };
    });
  };

  const apply = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      let count = 0;
      for (const index of [...selected].sort((a, b) => a - b)) {
        const row = rows[index];
        if (!row?.place) {
          continue;
        }
        const choice = choices[index] ?? choiceFor(row, row.place);
        await applyPhotoMatch(row, choice);
        count += 1;
      }
      if (!alive.current) {
        return;
      }
      setDone(
        count === 1
          ? "1 fotka je u návštěvy."
          : `${count} ${czechCountWord(count, "fotka", "fotky", "fotek")} ${count <= 4 ? "jsou" : "je"} u návštěv.`,
      );
      setRows([]);
      setSelected(new Set());
      setQueries({});
      setChoices({});
      await refreshVisits();
    } catch (err) {
      if (alive.current) {
        setError(err instanceof Error ? err.message : "Fotky se nepodařilo přiřadit.");
      }
    } finally {
      if (alive.current) {
        setBusy(false);
      }
    }
  };

  return (
    <section className="photo-intake">
      <h2>Fotky z výletu</h2>
      <p className="muted">
        Fotka se přidá k návštěvě místa, ne k výletu. Když ten den návštěva není, vyberte existující (třeba o den
        zpět) nebo založte novou s datem. Z GPS nabídneme místo do {PHOTO_SUGGEST_MAX_KM} km; do{" "}
        {Math.round(PHOTO_MATCH_MAX_KM * 1000)} m ho předvybereme.
      </p>
      <label className="file-picker">
        Vybrat fotky
        <input
          type="file"
          accept="image/jpeg,image/jpg,image/*"
          multiple
          onChange={(event) => void onFiles(event.target.files)}
        />
      </label>
      {busy ? <p className="muted">Zpracovávám…</p> : null}
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {done ? (
        <p className="notice" role="status">
          {done}
        </p>
      ) : null}
      {rows.length > 0 ? (
        <>
          <ul className="place-list photo-intake-list">
            {rows.map((row, index) => (
              <PhotoIntakeRow
                key={`${row.file.name}-${index}`}
                row={row}
                index={index}
                checked={selected.has(index)}
                query={queries[index] ?? ""}
                choice={
                  row.place ? (choices[index] ?? choiceFor(row, row.place)) : { kind: "create", visitedAt: row.visitedAt }
                }
                visits={visits}
                today={today}
                places={places}
                onToggle={(checked) => {
                  setSelected((current) => {
                    const next = new Set(current);
                    if (checked) {
                      next.add(index);
                    } else {
                      next.delete(index);
                    }
                    return next;
                  });
                }}
                onQuery={(value) => setQueries((current) => ({ ...current, [index]: value }))}
                onAssign={(place, km) => assignPlace(index, place, km)}
                onChoice={(choice) => setChoices((current) => ({ ...current, [index]: choice }))}
              />
            ))}
          </ul>
          <button type="button" className="photo-intake-apply" onClick={() => void apply()} disabled={busy || selected.size === 0}>
            {busy ? "Ukládám…" : "Přiřadit vybrané"}
          </button>
        </>
      ) : null}
    </section>
  );
}

function PhotoIntakeRow({
  row,
  index,
  checked,
  query,
  choice,
  visits,
  today,
  places,
  onToggle,
  onQuery,
  onAssign,
  onChoice,
}: {
  row: PhotoPlaceMatch;
  index: number;
  checked: boolean;
  query: string;
  choice: PhotoVisitChoice;
  visits: StoredVisit[];
  today: string;
  places: CatalogPlace[];
  onToggle: (checked: boolean) => void;
  onQuery: (value: string) => void;
  onAssign: (place: CatalogPlace, km: number | null) => void;
  onChoice: (choice: PhotoVisitChoice) => void;
}) {
  const hits = useMemo(() => searchPlaces(places, query), [places, query]);
  const existing = row.place ? liveVisitsForPlace(visits, row.place.id) : [];
  const radioName = `photo-visit-${index}`;
  const checkboxId = `photo-intake-${index}`;
  const createDate = choice.kind === "create" ? choice.visitedAt : row.visitedAt;
  const existingId = choice.kind === "existing" ? choice.visitId : (existing[0]?.id ?? "");
  return (
    <li>
      <div className="photo-intake-row">
        <input
          id={checkboxId}
          type="checkbox"
          checked={checked}
          disabled={!row.place}
          onChange={(event) => onToggle(event.target.checked)}
        />
        <div className="photo-intake-copy">
          <label htmlFor={checkboxId}>
            <strong>{row.file.name}</strong>
            <span className="place-row-meta">{rowStatus(row)}</span>
          </label>
          {row.nearby.length > 0 ? (
            <label className="photo-intake-pick">
              Místo v okolí
              <select
                value={row.place?.id ?? ""}
                onChange={(event) => {
                  const hit = row.nearby.find((item) => item.place.id === event.target.value);
                  if (hit) {
                    onAssign(hit.place, hit.km);
                  }
                }}
              >
                <option value="">{row.place ? "Vybrat jiné z okolí" : "Vybrat místo z okolí"}</option>
                {row.place && !row.nearby.some((hit) => hit.place.id === row.place?.id) ? (
                  <option value={row.place.id}>{row.place.name}</option>
                ) : null}
                {row.nearby.map((hit) => (
                  <option key={hit.place.id} value={hit.place.id}>
                    {hit.place.name} · {metersLabel(hit.km)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label className="photo-intake-pick">
            {row.nearby.length > 0 ? "Jiné místo" : "Hledat místo"}
            <input
              type="search"
              value={query}
              onChange={(event) => onQuery(event.target.value)}
              placeholder="min. 3 písmena"
              autoComplete="off"
            />
          </label>
          {hits.length > 0 ? (
            <ul className="photo-intake-hits">
              {hits.map((place) => (
                <li key={place.id}>
                  <button type="button" className="ghost" onClick={() => onAssign(place, null)}>
                    {place.name}
                    {place.location.municipality ? ` · ${place.location.municipality}` : ""}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {row.place ? (
            <fieldset className="photo-intake-visit">
              <legend>Návštěva</legend>
              {existing.length > 0 ? (
                <label className="photo-intake-choice">
                  <input
                    type="radio"
                    name={radioName}
                    checked={choice.kind === "existing"}
                    onChange={() => onChoice({ kind: "existing", visitId: existingId || existing[0].id })}
                  />
                  <span>
                    Existující
                    <select
                      value={existingId}
                      onChange={(event) => onChoice({ kind: "existing", visitId: event.target.value })}
                      onFocus={() => {
                        if (choice.kind !== "existing" && existing[0]) {
                          onChoice({ kind: "existing", visitId: existing[0].id });
                        }
                      }}
                    >
                      {existing.map((visit) => (
                        <option key={visit.id} value={visit.id}>
                          {visitOptionLabel(visit, today, row.visitedAt)}
                        </option>
                      ))}
                    </select>
                  </span>
                </label>
              ) : null}
              <label className="photo-intake-choice">
                <input
                  type="radio"
                  name={radioName}
                  checked={choice.kind === "create" || existing.length === 0}
                  onChange={() => onChoice({ kind: "create", visitedAt: createDate })}
                />
                <span>
                  {existing.length > 0 ? "Nová s datem" : "Datum nové návštěvy"}
                  <input
                    type="date"
                    value={createDate}
                    onChange={(event) => onChoice({ kind: "create", visitedAt: event.target.value })}
                    onFocus={() => {
                      if (choice.kind !== "create") {
                        onChoice({ kind: "create", visitedAt: createDate });
                      }
                    }}
                  />
                </span>
              </label>
            </fieldset>
          ) : null}
        </div>
      </div>
    </li>
  );
}
