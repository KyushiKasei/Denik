import { useState } from "react";
import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { renderVisitPostcard, sharePostcardPng } from "../diary/postcard";

export function PostcardButton({ place, visit }: { place: CatalogPlace; visit: StoredVisit }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const share = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const blob = await renderVisitPostcard({ place, visit });
      await sharePostcardPng(blob, place.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Pohlednici se nepodařilo vytvořit.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="postcard-wrap">
      <button type="button" className="ghost" onClick={() => void share()} disabled={busy}>
        {busy ? "Kreslím…" : "Pohlednice"}
      </button>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
