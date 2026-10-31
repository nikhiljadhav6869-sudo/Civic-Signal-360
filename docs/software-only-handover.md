# Software-only handover

Updated 31 October 2026. CivicSignal 360 is a software prototype centered on water, with electricity, roads, drainage, waste and streetlights sharing investigation workflows. **No hardware purchase, sensor installation or device calibration is required.**

## Available now

- CSV imports, synthetic scenarios and citizen reports support software-only operation. Water pages and the laboratory show software data guidance instead of device-registration controls. An optional legacy ingestion API and isolated simulator remain for software-generated feeds.
- Citizen challenges can reopen a resolved case without creating duplicate complaints. Public explanations and configured update targets are separate from internal notes. Closing a case requires relevant evidence; analytical signals alone do not prove a physical leak.
- Staff have scoped assignments, investigation classifications, evidence records and current data-quality context. Notifications have visible in-app history. The optional SMTP transport records failures/retries rather than claiming delivery.
- Administration shows worker heartbeat, queued/failed jobs and configuration readiness. Temporary cleanup is disabled by default. An administrator must record an approved basis, preview eligible expired sessions/old uncommitted CSV previews, and explicitly confirm deletion. Version/fingerprint checks reject stale previews. Cases, photos, reports, audit and committed observations are excluded.
- English/Marathi coverage now includes more administration, laboratory, field and settings controls. The document language, skip link, selected accessible names and narrow-screen layouts have checks. User-authored text and raw analytical records are not automatically translated.
- The free deployment configuration uses external PostgreSQL for records and new private image bytes. [Deployment guide](render-free-deployment.md).

## Verification and remaining work

The full backend run passed 236 tests before database-backed images were added. The subsequent storage/migration/photo/backup run passed 19 tests, including the new image-persistence checks. See [verification](verification.md) and checked-in result files for browser/build results and the scope of each run. These are synthetic/local tests, not measured municipal outcomes.

Remaining external steps: sign in to Render, connect a Neon Free database privately, deploy, verify the real HTTPS address, check free-tier memory/usage and perform a hosted backup/restore drill. No public URL is claimed yet.

Remaining evaluation: native Marathi review, broader screen-reader/contrast/usability testing, independent security review, realistic imported-data evaluation and approved operational commitments. Some dynamic technical messages/analytical fields remain English. Full personal-data erasure/anonymization and legal retention governance are not provided by the limited temporary cleanup.

In-app notification delivery is available; actual email delivery is unverified and SMTP is unavailable on Render Free. A future HTTPS mail-provider integration would require separate implementation/configuration and recipient consent. Hardware integration is outside the requested scope, not unfinished project work.

## Local use

Use the existing start batch file or `.venv\Scripts\python.exe scripts/run.py`. `CHECK-SOFTWARE-SETUP.bat` checks the local frontend setup without modifying records. Environment variables must be set in the launcher/server environment; `.env.example` is a reference and is not loaded automatically. Keep the non-demo hosted database separate from the local synthetic demo.
