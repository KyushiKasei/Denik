import { useState } from "react";
import { loadThemePreference, persistAndApplyTheme, type ThemePreference } from "../theme";

const OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "system", label: "Systém" },
  { value: "light", label: "Světlý" },
  { value: "dark", label: "Tmavý" },
];

export function ThemeSwitch({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<ThemePreference>(() => loadThemePreference());
  return (
    <div
      className={compact ? "segmented cols-3 theme-switch is-compact" : "segmented cols-3 theme-switch"}
      role="group"
      aria-label="Vzhled"
    >
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          className={theme === option.value ? "active" : undefined}
          aria-pressed={theme === option.value}
          onClick={() => {
            persistAndApplyTheme(option.value);
            setTheme(option.value);
          }}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
