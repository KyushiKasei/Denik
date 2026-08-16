import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

/** Mimo Dropbox/OneDrive — jinak Windows EBUSY při rename deps_temp → deps. */
function viteCacheDir(): string {
  const localAppData = process.env.LOCALAPPDATA;
  const base = localAppData
    ? path.join(localAppData, "PamatkyDenik")
    : path.join(os.homedir(), "AppData", "Local", "PamatkyDenik");
  return path.join(base, "vite");
}

export default defineConfig({
  cacheDir: viteCacheDir(),
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icons/*.svg", "icons/*.png", "_redirects", "_headers"],
      manifest: {
        id: "pamatky-denik",
        name: "Památky — katalog",
        short_name: "Památky",
        description: "Osobní katalog hradů, zámků a historických míst. Katalog se nahrává souborem, ne z hostingu.",
        lang: "cs",
        dir: "ltr",
        theme_color: "#3d5a40",
        background_color: "#f6f3ee",
        display: "standalone",
        orientation: "portrait",
        start_url: "/",
        scope: "/",
        categories: ["travel", "navigation"],
        icons: [
          {
            src: "icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "icons/icon-maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/_/, /\/[^/?]+\.[^/]+$/],
        runtimeCaching: [
          {
            /* Jen naposledy prohlížené OSM dlaždice — ne balíček celé ČR. ~800 × 20–40 kB ≈ desítky MB. */
            urlPattern: /^https:\/\/[a-z]+\.tile\.openstreetmap\.org\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "osm-tiles",
              expiration: {
                maxEntries: 800,
                maxAgeSeconds: 60 * 60 * 24 * 14,
                purgeOnQuotaError: true,
              },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /^https:\/\/nominatim\.openstreetmap\.org\/.*/i,
            handler: "NetworkOnly",
          },
          {
            urlPattern: /^https:\/\/commons\.wikimedia\.org\/.*/i,
            handler: "NetworkFirst",
            options: {
              cacheName: "commons-images",
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 * 14 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@shared": path.resolve(rootDir, "../shared"),
    },
  },
  server: {
    port: 5173,
    host: "127.0.0.1",
  },
  preview: {
    port: 4173,
    host: "127.0.0.1",
  },
});
