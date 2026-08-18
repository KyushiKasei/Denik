export interface SharedGeo {
  latitude: number;
  longitude: number;
  label: string;
}

const COORD = /(-?\d{1,2}(?:\.\d+)?)[,\s]+(-?\d{1,3}(?:\.\d+)?)/;

function asGeo(lat: number, lon: number, label: string): SharedGeo | null {
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    return null;
  }
  return { latitude: lat, longitude: lon, label };
}

export function parseSharedGeo(raw: string | null | undefined): SharedGeo | null {
  const text = (raw || "").trim();
  if (!text) {
    return null;
  }
  try {
    const url = new URL(text);
    const host = url.hostname.replace(/^www\./, "");
    if (host.endsWith("mapy.cz")) {
      const x = Number(url.searchParams.get("x"));
      const y = Number(url.searchParams.get("y"));
      const fromXy = asGeo(y, x, "Mapy.cz");
      if (fromXy) {
        return fromXy;
      }
      const q = url.searchParams.get("q") || url.searchParams.get("query");
      if (q) {
        const match = COORD.exec(q.replace(/[NSEW]/gi, " "));
        if (match) {
          return asGeo(Number(match[1]), Number(match[2]), q);
        }
      }
    }
    if (host.endsWith("google.com") || host.endsWith("google.cz") || host.endsWith("goo.gl")) {
      const at = /@(-?\d+\.\d+),(-?\d+\.\d+)/.exec(url.href);
      if (at) {
        return asGeo(Number(at[1]), Number(at[2]), "Google Maps");
      }
      const q = url.searchParams.get("q") || url.searchParams.get("query") || "";
      const match = COORD.exec(q);
      if (match) {
        return asGeo(Number(match[1]), Number(match[2]), q);
      }
    }
    if (host.endsWith("apple.com") || url.protocol === "maps:") {
      const ll = url.searchParams.get("ll") || "";
      const match = COORD.exec(ll);
      if (match) {
        return asGeo(Number(match[1]), Number(match[2]), url.searchParams.get("q") || "Apple Maps");
      }
    }
    if (url.protocol === "geo:") {
      const match = COORD.exec(url.pathname.replace(";", " "));
      if (match) {
        return asGeo(Number(match[1]), Number(match[2]), "geo");
      }
    }
  } catch {
    const match = COORD.exec(text);
    if (match) {
      const a = Number(match[1]);
      const b = Number(match[2]);
      if (Math.abs(a) <= 90 && Math.abs(b) <= 180) {
        return asGeo(a, b, text.slice(0, 40));
      }
    }
  }
  return null;
}

export function shareQueryFromLocation(search: string): { title: string; text: string; url: string } {
  const params = new URLSearchParams(search);
  return {
    title: params.get("title") ?? "",
    text: params.get("text") ?? "",
    url: params.get("url") ?? "",
  };
}

export async function consumeSharedCache(): Promise<{
  title: string;
  text: string;
  url: string;
  files: File[];
} | null> {
  if (typeof caches === "undefined") {
    return null;
  }
  const cache = await caches.open("pamatky-share");
  const metaRes = await cache.match("/__share/meta");
  if (!metaRes) {
    return null;
  }
  const meta = (await metaRes.json()) as { title?: string; text?: string; url?: string; count?: number };
  const files: File[] = [];
  const count = Math.min(40, Number(meta.count) || 0);
  for (let index = 0; index < count; index += 1) {
    const res = await cache.match(`/__share/${index}`);
    if (!res) {
      continue;
    }
    const blob = await res.blob();
    const name = decodeURIComponent(res.headers.get("x-filename") || `share-${index}.jpg`);
    files.push(new File([blob], name, { type: blob.type || "image/jpeg" }));
  }
  const keys = await cache.keys();
  await Promise.all(keys.map((request) => cache.delete(request)));
  return {
    title: meta.title ?? "",
    text: meta.text ?? "",
    url: meta.url ?? "",
    files,
  };
}

