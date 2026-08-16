import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

function viteCacheDir(): string {
  const localAppData = process.env.LOCALAPPDATA;
  const base = localAppData
    ? path.join(localAppData, "PamatkyDenik")
    : path.join(os.homedir(), "AppData", "Local", "PamatkyDenik");
  return path.join(base, "vite");
}

export default defineConfig({
  cacheDir: viteCacheDir(),
  resolve: {
    alias: {
      "@shared": path.resolve(rootDir, "../shared"),
    },
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
    setupFiles: ["tests/setup.ts"],
    globals: false,
  },
});
