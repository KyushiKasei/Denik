import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { czechCountWord, uniqueVisitedPlaceIds } from "../diary/timeline";
import { parseGpxTrack, placesAlongTrack } from "../geo/gpx";
import { PlaceCard } from "./PlaceCard";
import { StampButton } from "./StampButton";

export function GpxTrack({
  places,
  visits,
  onStamped,
}: {
  places: CatalogPlace[];
  visits: StoredVisit[];
  onStamped?: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [hits, setHits] = useState<ReturnType<typeof placesAlongTrack>>([]);
  const alive = useRef(true);
  const visited = uniqueVisitedPlaceIds(visits);
  const missed = hits.filter((hit) => !visited.has(hit.place.id));

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const onFile = async (file: File | undefined) => {
    setError(null);
    setHits([]);
    setFileName(file?.name ?? null);
    if (!file) {
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setError("Soubor GPX je větší než 20 MB.");
      return;
    }
    try {
      const text = await file.text();
      if (!alive.current) {
        return;
      }
      const track = parseGpxTrack(text);
      setHits(placesAlongTrack(places, track));
    } catch (err) {
      if (alive.current) {
        setError(err instanceof Error ? err.message : "GPX se nepodařilo načíst.");
      }
    }
  };

  return (
    <section className="gpx-track">
      <h2>Stopa z výletu</h2>
      <p className="muted">
        Nahrajte GPX z Mapy.cz nebo hodinek. Ukážeme památky do 400 m od trasy, které ještě nemáte orazítkované.
      </p>
      <label className="file-picker">
        Vybrat GPX
        <input
          type="file"
          accept=".gpx,application/gpx+xml,application/xml,text/xml"
          onChange={(event) => void onFile(event.target.files?.[0])}
        />
      </label>
      {fileName ? <p className="muted">Soubor: {fileName}</p> : null}
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {hits.length > 0 ? (
        <>
          <p className="muted small">
            {hits.length} {czechCountWord(hits.length, "místo", "místa", "míst")} u stopy
            {missed.length ? ` · ${missed.length} bez razítka` : " · všechno už máte"}
          </p>
          <div className="place-cards">
            {missed.slice(0, 12).map((hit) => (
              <div key={hit.place.id}>
                <PlaceCard
                  place={hit.place}
                  to={`/place/${hit.place.id}?from=diary`}
                  metaExtra={`${Math.round(hit.km * 1000)} m od stopy`}
                />
                <StampButton placeId={hit.place.id} alreadyToday={false} size="compact" onStamped={onStamped} />
              </div>
            ))}
          </div>
          {missed.length === 0 ? (
            <p>
              <Link to="/diary?sec=visits">Všechna místa u stopy už v deníku jsou.</Link>
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
