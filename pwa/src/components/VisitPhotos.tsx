import { useEffect, useRef, useState } from "react";
import {
  addVisitPhoto,
  deleteVisitPhoto,
  loadPhotosForVisit,
  MAX_PHOTOS_PER_VISIT,
  type StoredVisitPhoto,
} from "../diary/photos";

export function VisitPhotos({ visitId }: { visitId: string }) {
  const [photos, setPhotos] = useState<StoredVisitPhoto[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [urls, setUrls] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const alive = useRef(true);
  const visitIdRef = useRef(visitId);
  visitIdRef.current = visitId;

  const reload = async (id: string) => {
    const rows = await loadPhotosForVisit(id);
    if (alive.current && visitIdRef.current === id) {
      setPhotos(rows);
    }
  };

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void loadPhotosForVisit(visitId)
      .then((rows) => {
        if (!cancelled) {
          setPhotos(rows);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Fotky se nepodařilo načíst.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [visitId]);

  useEffect(() => {
    const next = photos.map((photo) => URL.createObjectURL(photo.blob));
    setUrls(next);
    return () => {
      next.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [photos]);

  const onFile = async (file: File | undefined) => {
    if (!file || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await addVisitPhoto(visitId, file);
      await reload(visitId);
    } catch (err) {
      if (alive.current) {
        setError(err instanceof Error ? err.message : "Fotku se nepodařilo uložit.");
      }
    } finally {
      if (alive.current) {
        setBusy(false);
      }
    }
  };

  const remove = async (id: string) => {
    if (busy) {
      return;
    }
    setBusy(true);
    try {
      await deleteVisitPhoto(id);
      await reload(visitId);
    } catch {
      if (alive.current) {
        setError("Fotku se nepodařilo smazat.");
      }
    } finally {
      if (alive.current) {
        setBusy(false);
      }
    }
  };

  return (
    <div className="visit-photos">
      {urls.length > 0 ? (
        <ul className="visit-photo-grid">
          {photos.map((photo, index) => (
            <li key={photo.id}>
              <img src={urls[index]} alt="Fotka návštěvy" />
              <button type="button" className="ghost" onClick={() => void remove(photo.id)} disabled={busy}>
                Smazat
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {photos.length < MAX_PHOTOS_PER_VISIT ? (
        <label className="file-picker is-compact">
          Přidat fotku
          <input type="file" accept="image/*" capture="environment" disabled={busy} onChange={(event) => void onFile(event.target.files?.[0])} />
        </label>
      ) : null}
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
