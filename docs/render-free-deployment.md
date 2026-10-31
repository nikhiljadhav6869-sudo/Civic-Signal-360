# Free Render deployment

Prepared 31 October 2026. No hosted deployment or public URL is verified yet.

## Design and limits

Use **one Render Free web service** and **one Neon Free PostgreSQL project**. `render.yaml` provisions no paid worker, persistent disk or Render database. The web service runs the API and worker together. Records and new private photo bytes live in PostgreSQL; local files are disposable.

Render Free sleeps after 15 minutes without traffic, loses local files on restart and has usage limits. Its free PostgreSQL expires after 30 days, so do not select that database for this setup. SMTP ports are blocked on Free: use in-app notifications; outbound email is not verified here. See [Render Free documentation](https://render.com/docs/free).

Neon Free is currently $0/month with compute, storage and transfer quotas, and no uptime SLA. Photos count against database storage. See [Neon plans](https://neon.com/docs/introduction/plans). These are ongoing free tiers, **not a guarantee of permanent free hosting**. Keep accounts on Free and review usage. If a provider asks for payment or a paid upgrade, stop; it is outside this project's approved budget. Avoid adding a payment method or enabling paid overages for this deployment.

While Render sleeps, this application's worker also stops: queued analysis, retries and escalation checks wait until the application resumes. Worker activity is visible in Administration. There is no keep-alive workaround. Combined API/worker memory use on Render Free has not yet been measured; heavy analysis may exceed its resources.

## Account setup

1. Sign in to [Neon](https://console.neon.tech) and create a project on **Free**. Choose a region near the Render service. Use a new empty database, not the local synthetic demo database.
2. From Neon's connection dialog, copy the PostgreSQL connection string with its TLS parameters. Treat it as a password. Do not put it in Git, screenshots or chat.
3. Sign in to [Render](https://dashboard.render.com). Choose **New → Blueprint** and connect the Civic-Signal-360 repository. Select the branch containing `render.yaml` (the prepared branch is `codex/software-only-free-deployment`). Confirm the preview lists only one **Free web service**, no disk or database. If the branch is merged later, select the merged branch.
4. Enter the three requested secrets/settings in Render:

| Setting | Value |
|---|---|
| `DATABASE_URL` | Private Neon connection string; keep `sslmode=require` and supplied TLS options |
| `CIVIC_ADMIN_EMAIL` | Your administrator email |
| `CIVIC_ADMIN_PASSWORD` | New unique password, at least 14 characters; never the local demo password |

The blueprint sets `CIVIC_DEMO_MODE=false`, `COOKIE_SECURE=true`, `CIVIC_EVIDENCE_STORAGE=database` and the Render launcher. The launcher honors Render's `PORT`. `postgres://` and `postgresql://` URLs are normalized to the installed psycopg driver. Do not substitute a SQLite URL.

5. Create the service only after checking **Free**. Wait for the build, initial schema setup and healthy status. Open the exact HTTPS URL returned by Render; do not guess the address.
6. Set `CIVIC_PUBLIC_ORIGIN` to that HTTPS address if using `scripts/check_readiness.py --production`. This check inspects configuration only; it does not prove a public deployment works. Automatic deploys are off; publish later code changes deliberately.

## First use and verification

The hosted database starts empty with your private administrator account. Shared local demo accounts and demo scenario playback are disabled. Sign in with the administrator credentials, configure zones/assets/staff scopes through Administration, and import permitted CSV readings. No sensors or hardware are required. Local synthetic examples remain available in the separate local demo.

Before sharing the URL:

- Verify HTTPS, sign-in, sign-out and denied access without sign-in.
- Create a clearly marked test report, check its private receipt and authorized staff visibility.
- Upload a non-sensitive test image; verify an unrelated account cannot download it.
- Check Administration shows recent worker activity, then run a small permitted analysis.
- Restart the service and confirm the same report and image remain available.
- Test English/Marathi on a phone-size viewport and record the actual hosted results.
- Check Render and Neon usage; make a private database backup and test restoration into a separate database before accepting operational records.

These hosted checks remain pending. The local tests establish application behavior, not Render capacity or Neon reliability.

## Existing data, backups and updates

This deployment does **not** upload the user's existing local database, complaints or photographs. A separate reviewed migration is required to move them. Database-backed storage applies to newly uploaded images; old filesystem-backed images are still read locally and are not automatically moved into PostgreSQL.

Schema migration `0009_database_evidence_content` is additive. Back up before upgrading. PostgreSQL backups must include the `evidence_content` table because it contains image bytes. Keep backups private and outside the free service's ephemeral filesystem. Retain provider TLS settings and use a trusted PostgreSQL backup client. Do not paste credentials into shared terminal logs.

Do not downgrade to code predating migration 0009 while database-backed images are in use: older code cannot serve these bytes. Use a reviewed restore/migration plan instead. Temporary-data cleanup deliberately excludes cases, evidence, complaints, committed readings and audit history; it is not a mechanism for keeping within storage quotas by silently deleting records.
