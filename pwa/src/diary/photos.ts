import { db } from "../db";
import { persistStorage } from "../storage/persist";
import { newVisitId, nowIso } from "./ids";
import type { StoredVisitPhoto } from "./types";

export type { StoredVisitPhoto } from "./types";

export const MAX_PHOTOS_PER_VISIT = 3;
export const MAX_PHOTO_EDGE = 1280;
export const PHOTO_JPEG_QUALITY = 0.82;
export const MAX_PHOTO_BYTES = 8 * 1024 * 1024;

export async function loadPhotosForVisit(visitId: string): Promise<StoredVisitPhoto[]> {
  const rows = await db.visit_photos.where("visit_id").equals(visitId).toArray();
  return rows.sort((a, b) => a.created_at.localeCompare(b.created_at));
}

export async function loadAllPhotos(): Promise<StoredVisitPhoto[]> {
  return db.visit_photos.toArray();
}

export async function photoCountForVisit(visitId: string): Promise<number> {
  return db.visit_photos.where("visit_id").equals(visitId).count();
}

export async function compressImageFile(file: File, maxEdge = MAX_PHOTO_EDGE): Promise<Blob> {
  if (typeof createImageBitmap !== "function") {
    return file;
  }
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    return file;
  }
  try {
    const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return file;
    }
    ctx.drawImage(bitmap, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob((next) => resolve(next), "image/jpeg", PHOTO_JPEG_QUALITY);
    });
    return blob ?? file;
  } finally {
    bitmap.close();
  }
}

export async function addVisitPhoto(visitId: string, file: File): Promise<StoredVisitPhoto> {
  if (file.size > 20 * 1024 * 1024) {
    throw new Error("Fotka je větší než 20 MB.");
  }
  const count = await photoCountForVisit(visitId);
  if (count >= MAX_PHOTOS_PER_VISIT) {
    throw new Error(`U návštěvy mohou být nejvýš ${MAX_PHOTOS_PER_VISIT} fotky.`);
  }
  const blob = await compressImageFile(file);
  if (blob.size > MAX_PHOTO_BYTES) {
    throw new Error("Fotka je větší než 8 MB.");
  }
  const photo: StoredVisitPhoto = {
    id: newVisitId(),
    visit_id: visitId,
    mime: blob.type || "image/jpeg",
    blob,
    created_at: nowIso(),
  };
  await db.transaction("rw", db.visit_photos, async () => {
    const again = await photoCountForVisit(visitId);
    if (again >= MAX_PHOTOS_PER_VISIT) {
      throw new Error(`U návštěvy mohou být nejvýš ${MAX_PHOTOS_PER_VISIT} fotky.`);
    }
    await db.visit_photos.put(photo);
  });
  await persistStorage();
  return photo;
}

export async function addVisitPhotoBlob(
  visitId: string,
  blob: Blob,
  id?: string,
  createdAt?: string,
): Promise<StoredVisitPhoto> {
  const photo: StoredVisitPhoto = {
    id: id ?? newVisitId(),
    visit_id: visitId,
    mime: blob.type || "image/jpeg",
    blob,
    created_at: createdAt ?? nowIso(),
  };
  await db.visit_photos.put(photo);
  return photo;
}

export async function deleteVisitPhoto(id: string): Promise<void> {
  await db.visit_photos.delete(id);
  await persistStorage();
}

export async function deletePhotosForVisit(visitId: string): Promise<void> {
  await db.visit_photos.where("visit_id").equals(visitId).delete();
}

export function mimeFromPhotoZipName(name: string): string {
  const lower = name.replaceAll("\\", "/").toLowerCase();
  if (lower.endsWith(".png")) {
    return "image/png";
  }
  if (lower.endsWith(".webp")) {
    return "image/webp";
  }
  return "image/jpeg";
}

export function photoZipPath(photo: StoredVisitPhoto): string {
  const mime = photo.mime.toLowerCase();
  const ext = mime.includes("png") ? "png" : mime.includes("webp") ? "webp" : "jpg";
  return `photos/${photo.visit_id}/${photo.id}.${ext}`;
}

export function parsePhotoZipPath(name: string): { visitId: string; photoId: string } | null {
  const match = /^photos\/([0-9a-fA-F-]{36})\/([0-9a-fA-F-]{36})\.(jpe?g|png|webp)$/i.exec(name.replaceAll("\\", "/"));
  if (!match) {
    return null;
  }
  return { visitId: match[1], photoId: match[2] };
}
