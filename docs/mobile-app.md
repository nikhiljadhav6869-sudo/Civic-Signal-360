# iPhone and Android installation

CivicSignal 360 now includes an installable web app, a bilingual `/install` page, application icons, and a downloadable QR image. This is not an APK, IPA, App Store listing or Play Store listing. Native store publishing is a separate deliverable requiring the relevant developer accounts and signed builds.

## Public links

Render has assigned `https://civicsignal-360.onrender.com` to the Free service. The mobile changes must be deployed before these new routes are usable:

- Installation page for both platforms: `https://civicsignal-360.onrender.com/install`
- Downloadable QR: `https://civicsignal-360.onrender.com/api/v1/install/qr.png`

The QR opens the installation page; it cannot install software without the person's confirmation. Its destination comes only from `CIVIC_PUBLIC_ORIGIN` or Render's `RENDER_EXTERNAL_URL`, never a request's Host header. A public HTTPS address is required. Localhost/private origins are rejected and do not receive a shareable code. QR generation is local to the application: no third-party QR service receives the URL or user data.

## Installing

**iPhone/iPad:** open the installation page in Safari, use Share → Add to Home Screen, enable Open as Web App if offered, then Add. See [Apple instructions](https://support.apple.com/guide/iphone/iphea86e5236/ios).

**Android:** open the page in Chrome. Use the installation button when Chrome offers it, or Chrome's menu → Install and create shortcut / Add to Home screen → Install. See [Chrome instructions](https://support.google.com/chrome/answer/9658361?co=GENIE.Platform%3DAndroid&hl=en). Browser labels vary.

The installed icon opens the same authenticated application. The web app does not bypass sign-in, data permissions or browser permissions. Live operations require internet. Existing consent-based draft recovery remains available; private API responses and evidence are never cached by the service worker. Browser/device storage can be cleared by the OS. Free service sleep still applies after installation.

## Before sharing

Deploy the mobile commit, check `/install`, download the QR, scan it on a real iPhone and Android phone and complete Home Screen installation. Confirm sign-in, report submission and image uploads over HTTPS. Local browser checks do not establish physical-device installation or hosted persistence. No App Store/Play Store download or physical-phone acceptance is claimed until separately verified.

Icons are reproducible using `scripts/generate_app_icons.py`. The manifest is `apps/web/public/manifest.webmanifest`. The install routes are public but expose only the configured public URL and QR, never credentials or case data.
