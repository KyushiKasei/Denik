import type { CatalogPlace, StoredVisit } from "../catalog/types";
import { formatVisitDate } from "./timeline";
import { stampArtForPlace, STAMP_PATHS } from "./stampArt";

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

async function loadImage(url: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = () => resolve(null);
    image.src = url;
  });
}

export async function renderVisitPostcard(input: {
  place: CatalogPlace;
  visit: StoredVisit;
  photoUrl?: string | null;
}): Promise<Blob> {
  const width = 1080;
  const height = 1350;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Pohlednici nelze vykreslit.");
  }

  ctx.fillStyle = "#f4efe6";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#fffaf3";
  roundRect(ctx, 48, 48, width - 96, height - 96, 28);
  ctx.fill();

  const photoSrc = input.photoUrl ?? input.place.image?.original_url ?? input.place.image?.thumbnail_url;
  const image = photoSrc ? await loadImage(photoSrc) : null;
  if (image) {
    const boxX = 88;
    const boxY = 120;
    const boxW = width - 176;
    const boxH = 720;
    ctx.save();
    roundRect(ctx, boxX, boxY, boxW, boxH, 18);
    ctx.clip();
    const scale = Math.max(boxW / image.width, boxH / image.height);
    const dw = image.width * scale;
    const dh = image.height * scale;
    ctx.drawImage(image, boxX + (boxW - dw) / 2, boxY + (boxH - dh) / 2, dw, dh);
    ctx.restore();
  } else {
    ctx.fillStyle = "#e7efe4";
    roundRect(ctx, 88, 120, width - 176, 720, 18);
    ctx.fill();
  }

  const art = stampArtForPlace(input.place);
  ctx.save();
  ctx.translate(width - 280, 760);
  ctx.rotate((-8 * Math.PI) / 180);
  ctx.strokeStyle = art.wax;
  ctx.lineWidth = 6;
  ctx.beginPath();
  const path = new Path2D(STAMP_PATHS[art.kind]);
  ctx.scale(3.2, 3.2);
  ctx.stroke(path);
  ctx.restore();

  ctx.fillStyle = "#1e1a16";
  ctx.font = "700 54px Georgia, 'Iowan Old Style', serif";
  wrapText(ctx, input.place.name, 96, 920, width - 192, 64);
  ctx.fillStyle = "#6a6258";
  ctx.font = "32px Georgia, serif";
  const region = input.place.location.region ?? input.place.location.municipality ?? "";
  ctx.fillText(`${formatVisitDate(input.visit.visited_at)}${region ? ` · ${region}` : ""}`, 96, 1120);
  if (input.visit.note) {
    ctx.font = "italic 28px Georgia, serif";
    wrapText(ctx, input.visit.note, 96, 1180, width - 192, 36);
  }

  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob((next) => resolve(next), "image/png");
  });
  if (!blob) {
    throw new Error("Pohlednici se nepodařilo uložit.");
  }
  return blob;
}

function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
): void {
  const words = text.split(/\s+/);
  let line = "";
  let row = 0;
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > maxWidth && line) {
      ctx.fillText(line, x, y + row * lineHeight);
      line = word;
      row += 1;
      if (row >= 3) {
        ctx.fillText(`${word}…`, x, y + row * lineHeight);
        return;
      }
    } else {
      line = next;
    }
  }
  if (line) {
    ctx.fillText(line, x, y + row * lineHeight);
  }
}

export async function sharePostcardPng(blob: Blob, title: string): Promise<void> {
  const file = new File([blob], "pohlednice.png", { type: "image/png" });
  const nav = navigator as Navigator & {
    canShare?: (data: ShareData) => boolean;
    share?: (data: ShareData) => Promise<void>;
  };
  if (typeof nav.share === "function") {
    const payload: ShareData = { files: [file], title, text: title };
    let can = true;
    if (typeof nav.canShare === "function") {
      try {
        can = nav.canShare(payload);
      } catch {
        can = false;
      }
    }
    if (can) {
      try {
        await nav.share(payload);
        return;
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
      }
    }
  }
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "pohlednice.png";
  anchor.click();
  URL.revokeObjectURL(url);
}
