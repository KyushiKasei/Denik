import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import { App } from "./App";
import { persistStorage } from "./storage/persist";
import { bootTheme } from "./theme";
import "./styles.css";

registerSW({ immediate: true });
bootTheme();
void persistStorage();

const root = document.getElementById("root");
if (!root) {
  throw new Error("Chybí #root");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
