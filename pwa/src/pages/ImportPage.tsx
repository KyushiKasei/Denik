import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CatalogImportError } from "../catalog/errors";
import { loadCatalogMeta, loadPlaces, previewCatalogImport, replacePlacesStore, catalogVersionAlreadyLoaded, type CatalogMeta } from "../catalog/importCatalog";
import type { Catalog, CatalogDiff, CatalogPlace } from "../catalog/types";
import { FirstRunCoach } from "../components/FirstRunCoach";
import { PhotoIntake } from "../components/PhotoIntake";
import { SyncStatus } from "../components/SyncStatus";
import { ThemeSwitch } from "../components/ThemeSwitch";
import { DiaryImportError } from "../diary/errors";
import { countVisitsForRemovedPlaces, listOrphanedDiary } from "../diary/orphans";
import { downloadDiaryBundle, importDiary, importDiaryPhotos, loadDiaryMeta, loadVisits } from "../diary/store";
import { inspectIncomingFile } from "../diary/fileIntake";
import type { Diary, DiaryMergeCounts, DiaryMeta } from "../diary/types";
import { consumeSharedCache, parseSharedGeo, shareQueryFromLocation } from "../geo/shareTarget";
import { czechCountWord, formatDateTime } from "../diary/timeline";

export function ImportPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [familyMerge, setFamilyMerge] = useState(false);
  const [sharedFiles, setSharedFiles] = useState<File[] | undefined>(undefined);
  const [shareHint, setShareHint] = useState<string | null>(null);
  const [currentVersion, setCurrentVersion] = useState<number | null>(null);
  const [catalogMeta, setCatalogMeta] = useState<CatalogMeta | null>(null);
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
  const [exportBusy, setExportBusy] = useState(false);
  const [diaryResult, setDiaryResult] = useState<DiaryMergeCounts | null>(null);
  const [orphanVisitCount, setOrphanVisitCount] = useState(0);
  const [existingOrphans, setExistingOrphans] = useState(0);
  const [diaryPhotoCount, setDiaryPhotoCount] = useState(0);
  const [dropHint, setDropHint] = useState(false);
  const [metaReady, setMetaReady] = useState(false);
  const [zipEntries, setZipEntries] = useState<Array<{ name: string; data: Uint8Array }> | null>(null);
  const [places, setPlaces] = useState<CatalogPlace[]>([]);
  const redirectTimer = useRef(0);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void loadCatalogMeta()
      .then((meta) => {
        if (cancelled) {
          return;
        }
        setCatalogMeta(meta);
        setCurrentVersion(meta.catalog_version);
        setMetaReady(true);
      })
      .catch(() => {
        if (!cancelled) {
          setError("Stav katalogu se nepodařilo načíst.");
        }
      });
    void loadDiaryMeta()
      .then((meta) => {
        if (!cancelled) {
          setDiaryMeta(meta);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDiaryError("Stav deníku se nepodařilo načíst.");
        }
      });
    void listOrphanedDiary()
      .then((groups) => {
        if (!cancelled) {
          setExistingOrphans(groups.length);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDiaryError("Seznam osiřelých záznamů se nepodařilo načíst.");
        }
      });
    void loadPlaces()
      .then((rows) => {
        if (!cancelled) {
          setPlaces(rows);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDiaryError("Katalog se nepodařilo načíst pro přiřazení fotek.");
        }
      });
    return () => {
      cancelled = true;
      window.clearTimeout(redirectTimer.current);
    };
  }, []);

  useEffect(() => {
    const query = shareQueryFromLocation(searchParams.toString());
    const geo = parseSharedGeo(query.url || query.text);
    if (geo) {
      navigate(`/map?lat=${geo.latitude}&lon=${geo.longitude}&origin_label=${encodeURIComponent(geo.label)}`, { replace: true });
      return;
    }
    const fromShareTarget = searchParams.get("shared") === "1";
    if (query.title.trim() && !query.url && !query.text && !fromShareTarget) {
      navigate(`/catalog?q=${encodeURIComponent(query.title.trim())}`, { replace: true });
      return;
    }
    if (!fromShareTarget) {
      return;
    }
    let cancelled = false;
    void consumeSharedCache()
      .then((shared) => {
        if (cancelled || !shared) {
          return;
        }
        const fromShare = parseSharedGeo(shared.url || shared.text);
        if (fromShare) {
          navigate(`/map?lat=${fromShare.latitude}&lon=${fromShare.longitude}&origin_label=${encodeURIComponent(fromShare.label)}`, {
            replace: true,
          });
          return;
        }
        if (shared.files.length) {
          setSharedFiles(shared.files);
          setShareHint(
            `${shared.files.length} ${czechCountWord(shared.files.length, "sdílená fotka", "sdílené fotky", "sdílených fotek")}. Přiřaďte k návštěvám.`,
          );
        } else if (shared.title.trim()) {
          navigate(`/catalog?q=${encodeURIComponent(shared.title.trim())}`, { replace: true });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Sdílený soubor se nepodařilo načíst.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [navigate, searchParams]);

  const onIncoming = async (file: File | undefined) => {
    if (!file) {
      return;
    }
    const inspected = await inspectIncomingFile(file);
    if (inspected.kind === "catalog" && inspected.catalogText) {
      const { loadCatalogFromText } = await import("../catalog/validate");
      const parsed = loadCatalogFromText(inspected.catalogText);
      await onCatalogParsed(file.name, parsed);
      return;
    }
    if ((inspected.kind === "diary" || inspected.kind === "diary-zip") && inspected.diary) {
      setDiaryError(null);
      setDiaryResult(null);
      setDiary(inspected.diary);
      setDiaryFileName(file.name);
      setZipEntries(inspected.zipEntries ?? null);
      return;
    }
    throw new Error("Soubor není catalog.json, diary.json ani diary.zip.");
  };

  const onCatalogParsed = async (name: string, parsed: Catalog) => {
    setError(null);
    setDone(false);
    setCatalog(null);
    setDiff(null);
    setOrphanVisitCount(0);
    setFileName(name);
    const preview = await previewCatalogImport(parsed);
    const visits = await loadVisits();
    setCatalog(parsed);
    setDiff(preview);
    setOrphanVisitCount(countVisitsForRemovedPlaces(visits, preview.removedIds));
  };

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
      await onIncoming(file);
    } catch (err) {
      if (!alive.current) {
        return;
      }
      const message = err instanceof CatalogImportError ? err.message : err instanceof Error ? err.message : "Soubor se nepodařilo načíst.";
      setError(message);
    }
  };

  const apply = async () => {
    if (!catalog || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await replacePlacesStore(catalog);
      if (!alive.current) {
        return;
      }
      setDone(true);
      setCurrentVersion(catalog.catalog_version);
      setExistingOrphans((await listOrphanedDiary()).length);
      window.clearTimeout(redirectTimer.current);
      redirectTimer.current = window.setTimeout(() => {
        if (alive.current) {
          navigate("/");
        }
      }, 800);
    } catch (err) {
      if (alive.current) {
        setError(err instanceof Error ? err.message : "Import selhal.");
      }
    } finally {
      if (alive.current) {
        setBusy(false);
      }
    }
  };

  const onDiaryFile = async (file: File | undefined) => {
    setDiaryError(null);
    setDiaryResult(null);
    setDiary(null);
    setZipEntries(null);
    setDiaryFileName(file?.name ?? null);
    if (!file) {
      return;
    }
    try {
      await onIncoming(file);
    } catch (err) {
      if (!alive.current) {
        return;
      }
      const message = err instanceof DiaryImportError ? err.message : err instanceof Error ? err.message : "Soubor se nepodařilo načíst.";
      setDiaryError(message);
    }
  };

  const applyDiary = async () => {
    if (!diary || diaryBusy) {
      return;
    }
    setDiaryBusy(true);
    setDiaryError(null);
    try {
      const counts = await importDiary(diary, { family: familyMerge });
      const photos = zipEntries ? await importDiaryPhotos(zipEntries) : 0;
      if (!alive.current) {
        return;
      }
      setDiaryPhotoCount(photos);
      setDiaryResult(counts);
      setDiaryMeta(await loadDiaryMeta());
    } catch (err) {
      if (alive.current) {
        setDiaryError(err instanceof Error ? err.message : "Import deníku selhal.");
      }
    } finally {
      if (alive.current) {
        setDiaryBusy(false);
      }
    }
  };

  const exportNow = async () => {
    if (exportBusy) {
      return;
    }
    setExportBusy(true);
    setDiaryError(null);
    try {
      await downloadDiaryBundle();
      if (alive.current) {
        setDiaryMeta(await loadDiaryMeta());
      }
    } catch (err) {
      if (alive.current) {
        setDiaryError(err instanceof Error ? err.message : "Export deníku selhal.");
      }
    } finally {
      if (alive.current) {
        setExportBusy(false);
      }
    }
  };

  const sameVersion = catalog != null && catalogVersionAlreadyLoaded(currentVersion, catalog.catalog_version);

  return (
    <section
      className={dropHint ? "file-drop is-active" : "file-drop"}
      onDragOver={(event) => {
        event.preventDefault();
        setDropHint(true);
      }}
      onDragLeave={() => setDropHint(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDropHint(false);
        const file = event.dataTransfer.files?.[0];
        void onIncoming(file).catch((err: unknown) => {
          if (!alive.current) {
            return;
          }
          const message = err instanceof Error ? err.message : "Soubor se nepodařilo načíst.";
          setError(message);
        });
      }}
    >
      <header className="page-header">
        <h1>Nastavení</h1>
        <p className="muted">
          Deník a katalog z PC. Soubory jdou Dropboxem nebo Soubory, doma na Wi-Fi přes Safari (ne z PWA). Vzhled je na
          konci stránky.
        </p>
      </header>

      <h2>Výměna dat</h2>

      <SyncStatus catalog={catalogMeta} diary={diaryMeta} />

      {metaReady && currentVersion == null ? <FirstRunCoach /> : null}

      <h2>Deník</h2>
      <p className="muted">
        {diaryMeta?.last_export_at ? `Poslední export: ${formatDateTime(diaryMeta.last_export_at)}. ` : "Deník ještě nebyl exportován. "}
        {diaryMeta?.last_import_at ? `Poslední import: ${formatDateTime(diaryMeta.last_import_at)}.` : ""}
      </p>

      <div className="diff-card">
        <h2>Doma na Wi-Fi</h2>
        <p className="muted small">
          Safari z QR na PC je jen pošťák. Poznámky žijí v ikoně na ploše, ne v té Safari stránce. Stejná privátní síť, ne
          guest Wi-Fi.
        </p>
        <ol className="lan-steps">
          <li>Na PC v Administraci → Výměna dat zapněte domácí síť a naskenujte QR do Safari.</li>
          <li>Tady exportujte deník a soubor uložte do Souborů.</li>
          <li>V Safari zadejte PIN, nahrajte export, stáhněte sloučený diary.zip.</li>
          <li>Vraťte se sem a importujte stažený zip. Volitelně stáhněte i catalog.json.</li>
        </ol>
        <p>
          <button type="button" className="ghost" onClick={() => void exportNow()} disabled={exportBusy}>
            {exportBusy ? "Exportuji…" : "1. Exportovat deník pro Safari"}
          </button>
        </p>
      </div>

      <div className="diff-card">
        <h2>Přes Dropbox / Soubory</h2>
        <p className="muted small">
          Stejná složka, kterou na PC nastavíte v Administraci → Výměna dat. V iOS sdílecím listu zvolte Uložit do
          Dropboxu nebo Soubory.
        </p>
        <ol className="lan-steps">
          <li>Tady exportujte deník a uložte <code>diary.zip</code> do Dropboxu.</li>
          <li>Na PC stiskněte Sloučit deník ze složky.</li>
          <li>Tady vyberte <code>diary-z-pc.zip</code> z Dropboxu a importujte ho.</li>
        </ol>
        <p className="muted small">Katalog: na PC dejte catalog.json do složky, tady nahradit katalog.</p>
        <p>
          <button type="button" onClick={() => void exportNow()} disabled={exportBusy}>
            {exportBusy ? "Exportuji…" : "Exportovat deník do Dropboxu"}
          </button>
        </p>
      </div>

      <p className="muted small">Soubor z Wi-Fi i z Dropboxu vyberte tady.</p>
      <label className="file-picker">
        Vybrat diary.json, diary.zip nebo diary-z-pc.zip
        <input
          type="file"
          accept=".json,.zip,application/json,application/zip,text/plain"
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
            {zipEntries ? <li>fotky v ZIP: {zipEntries.filter((entry) => entry.name.startsWith("photos/")).length}</li> : null}
            <li>exportováno z: {diary.exported_from}</li>
          </ul>
          <p className="muted small">Sloučení podle ID. Stejný soubor dvakrát nevytvoří duplicity. Místo se z deníku nezakládá.</p>
          <label>
            <input type="checkbox" checked={familyMerge} onChange={(event) => setFamilyMerge(event.target.checked)} />
            Rodinné sloučení (stejné místo a den = jedno razítko)
          </label>
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
          {diaryPhotoCount > 0 ? <p>Fotky: {diaryPhotoCount} uložených k návštěvám.</p> : null}
          {diaryResult.familyCollapsed ? (
            <p>Rodinná razítka sloučená: {diaryResult.familyCollapsed}.</p>
          ) : null}
        </div>
      ) : null}

      <h2>Import katalogu z PC do PWA</h2>
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
          {existingOrphans > 0
            ? ` ${existingOrphans} ${czechCountWord(existingOrphans, "záznam", "záznamy", "záznamů")} deníku ${existingOrphans >= 2 && existingOrphans <= 4 ? "odkazují" : "odkazuje"} na místo, které už v katalogu není.`
            : ""}
        </p>
      ) : null}

      {existingOrphans > 0 && !done ? (
        <p className="orphan-banner" role="status">
          {`${existingOrphans} ${czechCountWord(existingOrphans, "místo", "místa", "míst")} z deníku už ${existingOrphans >= 2 && existingOrphans <= 4 ? "nejsou" : "není"} v katalogu.`}{" "}
          Návštěvy zůstávají na stránce Katalog.
        </p>
      ) : null}

      <PhotoIntake places={places} initialFiles={sharedFiles} />
      {shareHint ? (
        <p className="notice" role="status">
          {shareHint}
        </p>
      ) : null}

      <h2>Vzhled</h2>
      <p className="muted">Světlý, tmavý, nebo podle nastavení systému.</p>
      <ThemeSwitch />

      <p className="muted small">
        <Link to="/info">Info</Link>
      </p>
    </section>
  );
}
