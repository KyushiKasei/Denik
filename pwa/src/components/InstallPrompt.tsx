import { useEffect, useState } from "react";

const DISMISS_KEY = "pamatky.installPrompt.dismissed";

function isStandalone(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    ("standalone" in navigator && Boolean((navigator as Navigator & { standalone?: boolean }).standalone))
  );
}

function isIos(): boolean {
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

export function InstallPrompt() {
  const [visible, setVisible] = useState(false);
  const [iosHint, setIosHint] = useState(false);
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    if (isStandalone()) {
      return;
    }
    try {
      if (localStorage.getItem(DISMISS_KEY) === "1") {
        return;
      }
    } catch {
      // private mode
    }
    if (isIos()) {
      setIosHint(true);
      setVisible(true);
      return;
    }
    const onPrompt = (event: Event) => {
      event.preventDefault();
      setDeferred(event as BeforeInstallPromptEvent);
      setVisible(true);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  if (!visible) {
    return null;
  }

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      // private mode / quota
    }
    setVisible(false);
  };

  const install = async () => {
    if (!deferred) {
      return;
    }
    await deferred.prompt();
    await deferred.userChoice;
    setDeferred(null);
    setVisible(false);
  };

  return (
    <aside className="install-banner" role="status">
      <div>
        <strong>Přidat na plochu</strong>
        {iosHint ? (
          <p>V Safari: Sdílet → Přidat na plochu. Aplikace pak lépe udrží katalog i bez sítě.</p>
        ) : (
          <p>Nainstalujte si katalog jako aplikaci, ať v telefonu zůstane i bez sítě.</p>
        )}
      </div>
      <div className="install-actions">
        {deferred ? (
          <button type="button" onClick={() => void install()}>
            Přidat
          </button>
        ) : null}
        <button type="button" className="ghost" onClick={dismiss}>
          Teď ne
        </button>
      </div>
    </aside>
  );
}

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}
