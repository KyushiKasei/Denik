import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CatalogImportError } from "../catalog/errors";
import { loadCatalogMeta, previewCatalogImport, replacePlacesStore, catalogVersionAlreadyLoaded } from "../catalog/importCatalog";
import type { Catalog, CatalogDiff } from "../catalog/types";
import { FirstRunCoach } from "../components/FirstRunCoach";
import { DiaryImportError } from "../diary/errors";
import { countVisitsForRemovedPlaces, listOrphanedDiary } from "../diary/orphans";
import { downloadDiaryFile, exportDiary, importDiary, loadDiaryMeta, loadVisits } from "../diary/store";
import type { Diary, DiaryMergeCounts, DiaryMeta } from "../diary/types";

export function ImportPage() {
  const navigate = useNavigate();
  const [currentVersion, setCurrentVersion] = useState<number | null>(null);
  const [diaryMeta, setDiaryMeta] = useState<DiaryMeta | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [diff, setDiff] = useState<CatalogDiff | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const [diaryFileName, setDiaryFileName] = useState<string | null>(null);
  const [diary, setDiary] = useState<Diary | null>(null);
  const [diaryError, setDiaryError] = useState<string | null>(null);
  const [diaryBusy, setDiaryBusy] = useState(false);
  const [diaryResult, setDiaryResult] = useState<DiaryMergeCounts | null>(null);
  const [orphanVisitCount, setOrphanVisitCount] = useState(0);
  const [existingOrphans, setExistingOrphans] = useState(0);
  const [metaReady, setMetaReady] = useState(false);

  useEffect(() => {
    void loadCatalogMeta().then((meta) => {
      setCurrentVersion(meta.catalog_version);
      setMetaReady(true);
    });
    void loadDiaryMeta().then(setDiaryMeta);
    void listOrphanedDiary().then((groups) => setExistingOrphans(groups.length));
  }, []);

  const onFile = async (file: File | undefined) => {
    setError(null);
    setDone(false);
    setCatalog(null);
    setDiff(null);
    setOrphanVisitCount(0);
    setFileName(file?.name ?? null);
    if (!file) {
      return;
    }
    try {
      const text = await file.text();
      const { loadCatalogFromText } = await import("../catalog/validate");
      const parsed = loadCatalogFromText(text);
      const preview = await previewCatalogImport(parsed);
      const visits = await loadVisits();
      setCatalog(parsed);
      setDiff(preview);
      setOrphanVisitCount(countVisitsForRemovedPlaces(visits, preview.removedIds));
    } catch (err) {
      const message = err instanceof CatalogImportError ? err.message : "Soubor se nepodařilo načíst.";
      setError(message);
    }
  };

  const apply = async () => {
    if (!catalog) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await replacePlacesStore(catalog);
      setDone(true);
      setCurrentVersion(catalog.catalog_version);
      setExistingOrphans((await listOrphanedDiary()).length);
      window.setTimeout(() => navigate("/"), 800);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import selhal.");
    } finally {
      setBusy(false);
    }
  };

  const onDiaryFile = async (file: File | undefined) => {
    setDiaryError(null);
    setDiaryResult(null);
    setDiary(null);
    setDiaryFileName(file?.name ?? null);
    if (!file) {
      return;
    }
    try {
      const text = await file.text();
      const { loadDiaryFromText } = await import("../diary/validate");
      setDiary(loadDiaryFromText(text));
    } catch (err) {
      const message = err instanceof DiaryImportError ? err.message : "Soubor se nepodařilo načíst.";
      setDiaryError(message);
    }
  };

  const applyDiary = async () => {
    if (!diary) {
      return;
    }
    setDiaryBusy(true);
    setDiaryError(null);
    try {
      const counts = await importDiary(diary);
      setDiaryResult(counts);
      setDiaryMeta(await loadDiaryMeta());
    } catch (err) {
      setDiaryError(err instanceof Error ? err.message : "Import deníku selhal.");
    } finally {
      setDiaryBusy(false);
    }
  };

  const exportNow = async () => {
    const file = await exportDiary();
    await downloadDiaryFile(file);
    setDiaryMeta(await loadDiaryMeta());
  };

  const sameVersion = catalog != null && catalogVersionAlreadyLoaded(currentVersion, catalog.catalog_version);

  return (
    <section>
      <header className="page-header">
        <h1>Soubory</h1>
        <p className="muted">Katalog a deník se přenášejí soubory. Mezi PC a telefonem není server.</p>
      </header>

      {metaReady && currentVersion == null ? <FirstRunCoach /> : null}

      <h2>Katalog</h2>
      <p className="muted">
        {currentVersion != null ? `Aktuální verze ${currentVersion}. ` : "Katalog ještě není nahraný. "}
        Nahraje se jen seznam míst. Osobní deník se nemění.
      </p>

      <label className="file-picker">
        Vybrat catalog.json
        <input
          type="file"
          accept=".json,application/json,text/plain"
          onChange={(event) => void onFile(event.target.files?.[0])}
        />
      </label>

      {fileName ? <p className="muted">Soubor: {fileName}</p> : null}
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}

      {catalog && diff ? (
        <div className="diff-card">
          <h2>Náhled změn</h2>
          {sameVersion ? (
            <p className="notice">
              Tuto verzi katalogu už máte ({catalog.catalog_version}). Nahrávat znovu není potřeba.
            </p>
          ) : null}
          <ul className="diff-counts">
            <li>verze souboru: {catalog.catalog_version}</li>
            <li>míst v souboru: {catalog.places.length}</li>
            <li>nová: {diff.added}</li>
            <li>změněná: {diff.changed}</li>
            <li>beze změny: {diff.unchanged}</li>
            <li>zmizelá z katalogu: {diff.removed}</li>
            {orphanVisitCount > 0 ? (
              <li>návštěv u zmizelých míst: {orphanVisitCount} (zůstanou, označí se jako osiřelé)</li>
            ) : null}
          </ul>
          <p className="muted small">Nahradí se jen úložiště míst. Návštěvy a stavy deníku zůstanou.</p>
          {sameVersion ? (
            <button type="button" className="ghost" onClick={() => void apply()} disabled={busy}>
              {busy ? "Nahrávám…" : "Přesto nahradit"}
            </button>
          ) : (
            <button type="button" onClick={() => void apply()} disabled={busy}>
              {busy ? "Nahrávám…" : "Nahradit katalog"}
            </button>
          )}
        </div>
      ) : null}

      {done ? (
        <p className="notice" role="status">
          Katalog je uložený.
          {existingOrphans > 0 ? ` ${existingOrphans} záznamů deníku odkazuje na místo, které už v katalogu není.` : ""}
        </p>
      ) : null}

      {existingOrphans > 0 && !done ? (
        <p className="orphan-banner" role="status">
          {existingOrphans === 1
            ? "1 místo z deníku už není v katalogu."
            : `${existingOrphans} míst z deníku už není v katalogu.`}{" "}
          Návštěvy zůstávají na stránce Katalog.
        </p>
      ) : null}

      <h2>Deník</h2>
      <p className="muted">
        {diaryMeta?.last_export_at ? `Poslední export: ${diaryMeta.last_export_at}. ` : "Deník ještě nebyl exportován. "}
        {diaryMeta?.last_import_at ? `Poslední import: ${diaryMeta.last_import_at}.` : ""}
      </p>
      <p>
        <button type="button" className="ghost" onClick={() => void exportNow()}>
          Exportovat diary.json
        </button>
      </p>

      <label className="file-picker">
        Vybrat diary.json
        <input
          type="file"
          accept=".json,application/json,text/plain"
          onChange={(event) => void onDiaryFile(event.target.files?.[0])}
        />
      </label>
      {diaryFileName ? <p className="muted">Soubor: {diaryFileName}</p> : null}
      {diaryError ? (
        <p className="error" role="alert">
          {diaryError}
        </p>
      ) : null}

      {diary ? (
        <div className="diff-card">
          <h2>Náhled deníku</h2>
          <ul className="diff-counts">
            <li>návštěv v souboru: {diary.visits.length}</li>
            <li>stavů míst: {diary.place_states.length}</li>
            <li>výletů: {diary.trips?.length ?? 0}</li>
            <li>exportováno z: {diary.exported_from}</li>
          </ul>
          <p className="muted small">Sloučení podle ID. Stejný soubor dvakrát nevytvoří duplicity. Místo se z deníku nezakládá.</p>
          <button type="button" onClick={() => void applyDiary()} disabled={diaryBusy}>
            {diaryBusy ? "Slučuji…" : "Importovat deník"}
          </button>
        </div>
      ) : null}

      {diaryResult ? (
        <div className="notice" role="status">
          <p>
            Návštěvy: +{diaryResult.visitsInserted} nové, {diaryResult.visitsUpdated} aktualizované,{" "}
            {diaryResult.visitsUnchanged} beze změny.
          </p>
          <p>
            Stavy míst: +{diaryResult.statesInserted} nové, {diaryResult.statesUpdated} aktualizované,{" "}
            {diaryResult.statesUnchanged} beze změny.
          </p>
          <p>
            Výlety: +{diaryResult.tripsInserted} nové, {diaryResult.tripsUpdated} aktualizované,{" "}
            {diaryResult.tripsUnchanged} beze změny.
          </p>
        </div>
      ) : null}
    </section>
  );
}
