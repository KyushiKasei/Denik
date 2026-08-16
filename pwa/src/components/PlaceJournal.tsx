import { useEffect, useRef, useState, type FormEvent } from "react";
import type { StoredPlaceState, StoredVisit } from "../catalog/types";
import {
  addVisit,
  loadPlaceState,
  loadVisitsForPlace,
  savePlaceState,
  softDeleteVisit,
  updateVisit,
} from "../diary/store";
import { todayIsoDate } from "../diary/ids";

function stars(rating: number | null): string {
  if (!rating) {
    return "—";
  }
  return "★".repeat(rating) + "☆".repeat(5 - rating);
}

type NoteStatus = "idle" | "saving" | "saved";

export function PlaceJournal({ placeId }: { placeId: string }) {
  const [visits, setVisits] = useState<StoredVisit[] | null>(null);
  const [state, setState] = useState<StoredPlaceState | null>(null);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [visitedAt, setVisitedAt] = useState(todayIsoDate());
  const [rating, setRating] = useState<string>("");
  const [people, setPeople] = useState("");
  const [note, setNote] = useState("");
  const [personalNote, setPersonalNote] = useState("");
  const [noteStatus, setNoteStatus] = useState<NoteStatus>("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const personalNoteRef = useRef("");
  const savedNoteRef = useRef<string | null>(null);
  const placeIdRef = useRef(placeId);

  personalNoteRef.current = personalNote;
  placeIdRef.current = placeId;

  const reload = async () => {
    const [rows, journal] = await Promise.all([loadVisitsForPlace(placeId), loadPlaceState(placeId)]);
    setVisits(rows);
    setState(journal ?? null);
    const stored = journal?.personal_note ?? "";
    setPersonalNote(stored);
    savedNoteRef.current = stored;
  };

  const persistNote = async (id: string = placeIdRef.current) => {
    const value = personalNoteRef.current.trim() || null;
    const saved = savedNoteRef.current?.trim() || null;
    if (value === saved) {
      return;
    }
    setNoteStatus("saving");
    const next = await savePlaceState(id, { personal_note: value });
    savedNoteRef.current = next.personal_note ?? "";
    setState(next);
    setNoteStatus("saved");
  };

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [rows, journal] = await Promise.all([loadVisitsForPlace(placeId), loadPlaceState(placeId)]);
      if (!cancelled) {
        setVisits(rows);
        setState(journal ?? null);
        const stored = journal?.personal_note ?? "";
        setPersonalNote(stored);
        savedNoteRef.current = stored;
        setNoteStatus("idle");
        setOpen(false);
        setEditingId(null);
        setError(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [placeId]);

  useEffect(() => {
    const previousId = placeId;
    const onHide = () => {
      if (document.visibilityState === "hidden") {
        void persistNote(previousId);
      }
    };
    const onPageHide = () => {
      void persistNote(previousId);
    };
    document.addEventListener("visibilitychange", onHide);
    window.addEventListener("pagehide", onPageHide);
    return () => {
      document.removeEventListener("visibilitychange", onHide);
      window.removeEventListener("pagehide", onPageHide);
      void persistNote(previousId);
    };
  }, [placeId]);

  const toggleFlag = async (field: "want_to_visit" | "favorite") => {
    const next = !(state?.[field] ?? false);
    const saved = await savePlaceState(placeId, { [field]: next });
    setState(saved);
  };

  const resetVisitForm = () => {
    setOpen(false);
    setEditingId(null);
    setRating("");
    setPeople("");
    setNote("");
    setVisitedAt(todayIsoDate());
    setError(null);
  };

  const startEdit = (visit: StoredVisit) => {
    setEditingId(visit.id);
    setOpen(true);
    setVisitedAt(visit.visited_at ?? todayIsoDate());
    setRating(visit.rating != null ? String(visit.rating) : "");
    setPeople(visit.people.join(", "));
    setNote(visit.note ?? "");
    setError(null);
  };

  const startAdd = () => {
    setEditingId(null);
    setOpen(true);
    setVisitedAt(todayIsoDate());
    setRating("");
    setPeople("");
    setNote("");
    setError(null);
  };

  const parseRating = (): number | null => {
    if (rating === "") {
      return null;
    }
    const ratingValue = Number(rating);
    if (ratingValue < 1 || ratingValue > 5) {
      throw new Error("Hodnocení musí být 1–5.");
    }
    return ratingValue;
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload = {
        visited_at: visitedAt || null,
        rating: parseRating(),
        people,
        note,
      };
      if (editingId) {
        await updateVisit(editingId, payload);
      } else {
        await addVisit({ place_id: placeId, ...payload });
      }
      resetVisitForm();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Návštěvu se nepodařilo uložit.");
    } finally {
      setBusy(false);
    }
  };

  const markVisitedToday = async () => {
    const today = todayIsoDate();
    const existing = visits?.find((visit) => visit.visited_at === today);
    if (existing) {
      startEdit(existing);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await addVisit({ place_id: placeId, visited_at: today, rating: null, people: "", note: null });
      resetVisitForm();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Návštěvu se nepodařilo uložit.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm("Smazat tuto návštěvu? Záznam zůstane v deníku jako smazaný a přenese se při exportu.")) {
      return;
    }
    await softDeleteVisit(id);
    if (editingId === id) {
      resetVisitForm();
    }
    await reload();
  };

  const today = todayIsoDate();
  const hasToday = Boolean(visits?.some((visit) => visit.visited_at === today));

  return (
    <section className="journal">
      <h2>Můj deník</h2>
      <div className="journal-flags">
        <label>
          <input
            type="checkbox"
            checked={Boolean(state?.want_to_visit)}
            onChange={() => void toggleFlag("want_to_visit")}
          />
          Chci navštívit
        </label>
        <label>
          <input type="checkbox" checked={Boolean(state?.favorite)} onChange={() => void toggleFlag("favorite")} />
          Oblíbené
        </label>
      </div>
      <label>
        Osobní poznámka
        <textarea
          value={personalNote}
          onChange={(event) => {
            setPersonalNote(event.target.value);
            setNoteStatus("idle");
          }}
          onBlur={() => void persistNote()}
          rows={3}
        />
      </label>
      <p className="muted small note-status" aria-live="polite">
        {noteStatus === "saving" ? "Ukládám…" : noteStatus === "saved" ? "Uloženo" : "Uloží se samo."}
      </p>

      <h3>Návštěvy</h3>
      {visits == null ? <p className="muted">Načítám návštěvy…</p> : null}
      {visits && visits.length === 0 ? <p className="muted">Zatím žádná návštěva.</p> : null}
      {visits && visits.length > 0 ? (
        <ul className="visit-list">
          {visits.map((visit) => (
            <li key={visit.id}>
              <div>
                <strong>{visit.visited_at ?? "bez data"}</strong>
                <span className="muted"> {stars(visit.rating)}</span>
                {visit.people.length > 0 ? <p className="muted">{visit.people.join(", ")}</p> : null}
                {visit.note ? <p>{visit.note}</p> : null}
              </div>
              <div className="visit-actions">
                <button type="button" className="ghost" onClick={() => startEdit(visit)}>
                  Upravit
                </button>
                <button type="button" className="ghost" onClick={() => void remove(visit.id)}>
                  Smazat
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {open ? (
        <form className="visit-form" onSubmit={(event) => void submit(event)}>
          <label>
            Datum
            <input type="date" value={visitedAt} onChange={(event) => setVisitedAt(event.target.value)} required />
          </label>
          <label>
            Hodnocení
            <div className="star-rating" role="radiogroup" aria-label="Hodnocení 1 až 5">
              {[1, 2, 3, 4, 5].map((value) => {
                const selected = Number(rating) >= value;
                const current = rating === String(value);
                return (
                  <button
                    key={value}
                    type="button"
                    className={selected ? "star selected" : "star"}
                    role="radio"
                    aria-checked={current}
                    aria-label={`${value} z 5`}
                    onClick={() => setRating(current ? "" : String(value))}
                  >
                    {selected ? "★" : "☆"}
                  </button>
                );
              })}
            </div>
          </label>
          <label>
            Kdo tam byl
            <input
              type="text"
              value={people}
              onChange={(event) => setPeople(event.target.value)}
              placeholder="Jana, Petr"
            />
          </label>
          <label>
            Poznámka
            <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} />
          </label>
          {error ? (
            <p className="error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="actions-row">
            <button type="submit" disabled={busy}>
              {busy ? "Ukládám…" : editingId ? "Uložit změny" : "Uložit návštěvu"}
            </button>
            <button type="button" className="ghost" onClick={resetVisitForm}>
              Zrušit
            </button>
          </div>
        </form>
      ) : (
        <div className="actions-row">
          <button type="button" onClick={() => void markVisitedToday()} disabled={busy}>
            {hasToday ? "Dnešní návštěva" : "Navštíveno dnes"}
          </button>
          <button type="button" className="ghost" onClick={startAdd}>
            Přidat návštěvu
          </button>
        </div>
      )}
    </section>
  );
}
