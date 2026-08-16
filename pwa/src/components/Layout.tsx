import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { InstallPrompt } from "./InstallPrompt";
import { ExportReminder } from "./ExportReminder";

export function Layout() {
  const [exportActive, setExportActive] = useState(false);
  return (
    <div className="app-shell">
      <ExportReminder onActiveChange={setExportActive} />
      {exportActive ? null : <InstallPrompt />}
      <main className="app-main">
        <Outlet />
      </main>
      <nav className="tab-bar" aria-label="Hlavní navigace">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "tab active" : "tab")}>
          Katalog
        </NavLink>
        <NavLink to="/map" className={({ isActive }) => (isActive ? "tab active" : "tab")}>
          Mapa
        </NavLink>
        <NavLink to="/diary" className={({ isActive }) => (isActive ? "tab active" : "tab")}>
          Deník
        </NavLink>
        <NavLink to="/import" className={({ isActive }) => (isActive ? "tab active" : "tab")}>
          Soubory
        </NavLink>
        <NavLink to="/info" className={({ isActive }) => (isActive ? "tab active" : "tab")}>
          Info
        </NavLink>
      </nav>
    </div>
  );
}
