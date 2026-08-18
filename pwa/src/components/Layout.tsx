import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { ErrorBoundary } from "./ErrorBoundary";
import { InstallPrompt } from "./InstallPrompt";
import { ExportReminder } from "./ExportReminder";
import { StampExperienceProvider } from "./StampExperience";

export function Layout() {
  const [exportActive, setExportActive] = useState(false);
  const [crash, setCrash] = useState<string | null>(null);
  const location = useLocation();
  const diaryActive = location.pathname.startsWith("/diary") || location.pathname.startsWith("/yearbook");
  const settingsActive = location.pathname.startsWith("/import") || location.pathname.startsWith("/info");

  useEffect(() => {
    const fail = () => setCrash("Něco se nepovedlo. Obnovte stránku.");
    window.addEventListener("unhandledrejection", fail);
    window.addEventListener("error", fail);
    return () => {
      window.removeEventListener("unhandledrejection", fail);
      window.removeEventListener("error", fail);
    };
  }, []);

  return (
    <StampExperienceProvider>
      <div className="app-shell">
        {crash ? (
          <p className="error" role="alert">
            {crash}
          </p>
        ) : null}
        <ExportReminder onActiveChange={setExportActive} />
        {exportActive ? null : <InstallPrompt />}
        <main className="app-main">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
        <nav className="tab-bar" aria-label="Hlavní navigace">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "tab active" : "tab")}>
            Dnes
          </NavLink>
          <NavLink to="/catalog" className={({ isActive }) => (isActive ? "tab active" : "tab")}>
            Katalog
          </NavLink>
          <NavLink to="/map" className={({ isActive }) => (isActive ? "tab active" : "tab")}>
            Mapa
          </NavLink>
          <NavLink to="/diary" className={() => (diaryActive ? "tab active" : "tab")}>
            Deník
          </NavLink>
          <NavLink to="/import" className={() => (settingsActive ? "tab active" : "tab")}>
            Nastavení
          </NavLink>
        </nav>
      </div>
    </StampExperienceProvider>
  );
}
