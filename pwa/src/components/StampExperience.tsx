import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { getPlace, loadPlaces } from "../catalog/importCatalog";
import { computeBadges, type DiaryBadge } from "../diary/badges";
import { loadSeenBadgeIds, markBadgesSeen, newlyUnlockedBadges } from "../diary/badgeUnlock";
import { loadVisits, updateVisit } from "../diary/store";
import { uniquePeopleNames } from "../diary/people";
import { PeopleInput } from "./PeopleInput";
import { addVisitPhoto, MAX_PHOTOS_PER_VISIT } from "../diary/photos";
import { renderVisitPostcard, sharePostcardPng } from "../diary/postcard";
import { StampMark } from "./StampMark";
import { stampArtForPlace } from "../diary/stampArt";

interface StampSession {
  visit: StoredVisit;
  place: CatalogPlace | null;
}

interface StampExperienceValue {
  notifyStamped: (visit: StoredVisit, created: boolean) => void;
}

const StampExperienceContext = createContext<StampExperienceValue>({
  notifyStamped: () => undefined,
});

export function useStampExperience(): StampExperienceValue {
  return useContext(StampExperienceContext);
}

function tapHaptic(): void {
  try {
    navigator.vibrate?.(35);
  } catch {
    // iOS Safari často vibrate neumí
  }
}

export function StampExperienceProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<StampSession | null>(null);
  const [badge, setBadge] = useState<DiaryBadge | null>(null);
  const [people, setPeople] = useState("");
  const [note, setNote] = useState("");
  const [peopleNames, setPeopleNames] = useState<string[]>([]);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const revealBadges = useCallback(async () => {
    const [visits, places] = await Promise.all([loadVisits(), loadPlaces()]);
    const unlocked = newlyUnlockedBadges(computeBadges(visits, places), loadSeenBadgeIds());
    markBadgesSeen(computeBadges(visits, places));
    if (unlocked.length > 0) {
      setBadge(unlocked[unlocked.length - 1] ?? null);
    }
  }, []);

  const notifyStamped = useCallback(
    (visit: StoredVisit, created: boolean) => {
      if (!created) {
        return;
      }
      tapHaptic();
      void (async () => {
        try {
          const [place, allVisits] = await Promise.all([getPlace(visit.place_id), loadVisits()]);
          setPeople("");
          setNote("");
          setPhotoError(null);
          setPeopleNames(uniquePeopleNames(allVisits));
          setSession({ visit, place: place ?? null });
          await revealBadges();
        } catch {
          // Razítko je uložené; list se jen neotevře.
        }
      })();
    },
    [revealBadges],
  );

  const closeSheet = () => setSession(null);

  useEffect(() => {
    if (!session && !badge) {
      return;
    }
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const root = document.querySelector(".memory-sheet, .badge-unlock");
    const focusable = root?.querySelector<HTMLElement>("button, input, select, textarea, a[href]");
    focusable?.focus();
    const nodes = () =>
      [...(root?.querySelectorAll<HTMLElement>("button, input, select, textarea, a[href]") ?? [])].filter(
        (el) => !el.hasAttribute("disabled"),
      );
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSession(null);
        setBadge(null);
        return;
      }
      if (event.key !== "Tab" || !root) {
        return;
      }
      const list = nodes();
      if (list.length === 0) {
        return;
      }
      const first = list[0];
      const last = list[list.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [session, badge]);

  const saveMemory = async () => {
    if (!session || busy) {
      return;
    }
    setBusy(true);
    try {
      await updateVisit(session.visit.id, {
        visited_at: session.visit.visited_at,
        rating: session.visit.rating,
        people,
        note,
      });
      setSession(null);
    } catch (err) {
      setPhotoError(err instanceof Error ? err.message : "Vzpomínku se nepodařilo uložit.");
    } finally {
      setBusy(false);
    }
  };

  const onPhoto = async (file: File | undefined) => {
    if (!session || !file || busy) {
      return;
    }
    setBusy(true);
    setPhotoError(null);
    try {
      await addVisitPhoto(session.visit.id, file);
    } catch (err) {
      setPhotoError(err instanceof Error ? err.message : "Fotku se nepodařilo uložit.");
    } finally {
      setBusy(false);
    }
  };

  const shareCard = async () => {
    if (!session?.place || busy) {
      return;
    }
    setBusy(true);
    try {
      const blob = await renderVisitPostcard({ place: session.place, visit: session.visit });
      await sharePostcardPng(blob, session.place.name);
    } catch (err) {
      setPhotoError(err instanceof Error ? err.message : "Pohlednici se nepodařilo připravit.");
    } finally {
      setBusy(false);
    }
  };

  const art = stampArtForPlace(session?.place);
  const value = useMemo(() => ({ notifyStamped }), [notifyStamped]);

  return (
    <StampExperienceContext.Provider value={value}>
      {children}
      {session ? (
        <div className="memory-sheet" role="dialog" aria-modal="true" aria-labelledby="memory-sheet-title">
          <div className="memory-sheet-card">
            <StampMark kind={art.kind} wax={art.wax} size={72} title="Razítko" />
            <h2 id="memory-sheet-title">Razítko je v deníku</h2>
            <p className="muted">{session.place?.name ?? "Místo"} · jedna věta stačí, nebo zavřít.</p>
            <label>
              S kým
              <PeopleInput value={people} onChange={setPeople} names={peopleNames} id="stamp-people" />
            </label>
            <label>
              Jedna věta
              <input value={note} onChange={(event) => setNote(event.target.value)} maxLength={180} />
            </label>
            <label className="file-picker is-compact">
              Fotka — max. {MAX_PHOTOS_PER_VISIT}
              <input type="file" accept="image/*" capture="environment" disabled={busy} onChange={(event) => void onPhoto(event.target.files?.[0])} />
            </label>
            {photoError ? (
              <p className="error" role="alert">
                {photoError}
              </p>
            ) : null}
            <div className="actions-row">
              <button type="button" onClick={() => void saveMemory()} disabled={busy}>
                {busy ? "Ukládám…" : "Uložit k návštěvě"}
              </button>
              <button type="button" className="ghost" onClick={closeSheet}>
                Teď ne
              </button>
            </div>
            {session.place ? (
              <p>
                <button type="button" className="text-link" onClick={() => void shareCard()} disabled={busy}>
                  Poslat pohlednici
                </button>
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
      {badge && !session ? (
        <div className="badge-unlock" role="dialog" aria-modal="true" aria-labelledby="badge-unlock-title">
          <div className="badge-unlock-card">
            <p className="muted">Nový odznak</p>
            <h2 id="badge-unlock-title">{badge.title}</h2>
            <p className="muted">{badge.detail}</p>
            <button type="button" onClick={() => setBadge(null)}>
              Do pasu
            </button>
          </div>
        </div>
      ) : null}
    </StampExperienceContext.Provider>
  );
}
