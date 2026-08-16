# deploy-netlify

Cílová složka pro [Netlify Drop](https://app.netlify.com/drop).

Na Drop patří **jen prázdný app shell** (HTML, JS, CSS, manifest, service worker). `catalog.json` a `diary.json` sem nepatří — nahrávají se v PWA ze souboru (Dropbox / USB).

Příprava na vývojářském PC:

```powershell
.\scripts\pripravit-deploy-netlify.ps1
```

Skript postaví PWA a zkopíruje `pwa/dist` sem. Pak celou složku `deploy-netlify` přetáhni na Netlify Drop, na iPhonu otevři HTTPS URL v Safari a zvol Sdílet → Přidat na plochu.
