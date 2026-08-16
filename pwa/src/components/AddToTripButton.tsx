import { useState } from "react";
import { addPlaceToActiveTrip } from "../diary/store";
import type { TripOrigin } from "../diary/types";

export function AddToTripButton({
  placeId,
  origin,
}: {
  placeId: string;
  origin?: TripOrigin | null;
}) {
  const [status, setStatus] = useState<"idle" | "saving" | "done" | "error">("idle");

  const onClick = async () => {
    setStatus("saving");
    try {
      await addPlaceToActiveTrip(placeId, origin ?? null);
      setStatus("done");
    } catch {
      setStatus("error");
    }
  };

  return (
    <button type="button" className="ghost" onClick={() => void onClick()} disabled={status === "saving"}>
      {status === "done" ? "Na výletu" : status === "error" ? "Nepodařilo se" : "Na výlet"}
    </button>
  );
}
