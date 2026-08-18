import { useEffect, useRef, useState } from "react";
import { stampVisitToday } from "../diary/stamp";
import { useStampExperience } from "./StampExperience";

export function StampButton({
  placeId,
  alreadyToday,
  size = "hero",
  tripId,
  onStamped,
}: {
  placeId: string;
  alreadyToday: boolean;
  size?: "hero" | "compact";
  tripId?: string | null;
  onStamped?: (created: boolean) => void;
}) {
  const { notifyStamped } = useStampExperience();
  const [busy, setBusy] = useState(false);
  const [pop, setPop] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const popTimer = useRef<number>(0);
  const alive = useRef(true);
  const stamped = alreadyToday || pop;

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      window.clearTimeout(popTimer.current);
    };
  }, []);

  const press = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await stampVisitToday(placeId, tripId);
      if (!alive.current) {
        return;
      }
      if (result.created) {
        setPop(true);
        window.clearTimeout(popTimer.current);
        popTimer.current = window.setTimeout(() => {
          if (alive.current) {
            setPop(false);
          }
        }, 900);
        notifyStamped(result.visit, true);
      }
      onStamped?.(result.created);
    } catch (err) {
      if (alive.current) {
        setError(err instanceof Error ? err.message : "Razítko se nepodařilo uložit.");
      }
    } finally {
      if (alive.current) {
        setBusy(false);
      }
    }
  };

  return (
    <div className={size === "hero" ? "stamp-wrap" : "stamp-wrap is-compact"}>
      <button
        type="button"
        className={`stamp-button ${size === "compact" ? "is-compact" : ""} ${stamped ? "is-stamped" : ""} ${pop ? "is-pop" : ""}`}
        onClick={() => void press()}
        disabled={busy}
        aria-pressed={stamped}
      >
        <span className="stamp-face">{stamped ? "Dnes už razítko" : "Byl jsem tady"}</span>
      </button>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
