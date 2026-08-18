import { useEffect, useRef, useState } from "react";
import type { CatalogPlace } from "../catalog/types";
import { readPhotoExif } from "../diary/exif";
import { applyPhotoMatch, suggestPhotoMatches, type PhotoPlaceMatch } from "../diary/photoMatch";

const MAX_INTAKE_BYTES = 20 * 1024 * 1024;
const MAX_INTAKE_FILES = 40;

export function PhotoIntake({
  places,
  initialFiles,
}: {
  places: CatalogPlace[];
  initialFiles?: File[];
}) {
  const [rows, setRows] = useState<PhotoPlaceMatch[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const alive = useRef(true);
  const shareKey = (initialFiles ?? []).map((file) => `${file.name}:${file.size}`).join("|");

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

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
      const exifs = await Promise.all(usable.map((file) => readPhotoExif(file)));
      if (!alive.current) {
        return;
      }
      const next = suggestPhotoMatches(usable, places, exifs);
      setRows(next);
      setSelected(new Set(next.map((row, index) => (row.place ? index : -1)).filter((index) => index >= 0)));
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
        await applyPhotoMatch(row);
        count += 1;
      }
      if (!alive.current) {
        return;
      }
      setDone(count === 1 ? "1 fotka je u návštěvy." : `${count} fotek je u návštěv.`);
      setRows([]);
      setSelected(new Set());
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
        Z GPS a data v EXIF se nabídne nejbližší místo. Bez souřadnic ve fotce místo nehádáme.
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
          <ul className="place-list">
            {rows.map((row, index) => (
              <li key={`${row.file.name}-${index}`}>
                <label className="photo-intake-row">
                  <input
                    type="checkbox"
                    checked={selected.has(index)}
                    disabled={!row.place}
                    onChange={(event) => {
                      setSelected((current) => {
                        const next = new Set(current);
                        if (event.target.checked) {
                          next.add(index);
                        } else {
                          next.delete(index);
                        }
                        return next;
                      });
                    }}
                  />
                  <span>
                    <strong>{row.file.name}</strong>
                    <span className="place-row-meta">
                      {row.place
                        ? `${row.place.name}${row.km != null ? ` · ${Math.round(row.km * 1000)} m` : ""} · ${row.visitedAt}`
                        : "bez GPS v EXIF — přeskočeno"}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <button type="button" onClick={() => void apply()} disabled={busy || selected.size === 0}>
            {busy ? "Ukládám…" : "Přiřadit vybrané"}
          </button>
        </>
      ) : null}
    </section>
  );
}
