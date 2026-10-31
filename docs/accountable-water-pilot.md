# Accountable water pilot — operating guide

Updated 30 October 2026. This is a local prototype. Automated tests and the simulator do not establish field performance, Marathi usability, successful hardware connections, measured water savings or production reliability.

## What changed

- Complaints have a full UUID receipt, private authenticated tracking, a responsible department, an explicit unassigned queue, next action, last update and optional next-update target. The earlier short receipt is retained as `legacy_receipt`. Possession of either reference does not grant access.
- Citizen challenges reopen resolved/closed cases, retain evidence and timestamps, and use idempotency keys so retrying a lost response does not create another challenge. Old classifications cannot close the reopened case. Investigators must make a fresh inspection.
- Closure now requires either human-reviewed resolution supported by intervention and subsequent follow-up, or a documented site-verified false alert. A separate citizen-facing explanation is required. Internal decision reasons never populate the public explanation automatically. Earlier terminal records remain readable; no data is rewritten.
- Operators can send explicit public updates. Administrators configure domain/severity targets and the responsible team/supervisor. No target is preconfigured for new complaints. Targets are administrative plans, not municipal promises. Changes apply to future complaints/reopenings; the original basis stays with existing records.
- New bilingual core workbench: open work → assignment → inspection → classification → intervention → monitoring → follow-up → reviewed outcome. Existing Evidence Passport and offline field drafts remain available. Broad analytical/admin screens and free-text user content are not fully translated.
- Asset-bound water ingestion, device states, a simulator and opt-in email delivery attempts are implemented as described below.

| Area | Implemented | Verified here | Remaining validation/work |
|---|---|---|---|
| Complaint accountability | Private tracking, explicit ownership queue, configured targets, public updates, evidence-gated outcomes, disputes | Automated API and English/Marathi browser journeys, including a lost response after commit | Municipal target approval and staff/citizen pilot |
| Water investigation | Preserved detector context, separate current-data-quality view, manual site findings, intervention/follow-up | Synthetic complete repair and disproved-alert/dispute cases | Independent field verification and measured outcomes |
| Devices | Authenticated interval ingestion, units/timestamps, duplicates, contact states and recovery | Simulator plus invalid/delayed/conflicting reading tests | Physical gateway, calibration, clocks, connectivity and security provisioning |
| Notifications | In-app updates and opted-in SMTP attempts/history/retry | Failure, retry and ownership tests using a substituted transport | Real provider delivery, recipient consent and bounce processing |
| Usability | Bilingual core forms/statuses, focused queue, responsive controls and explicit unconfirmed retries | English/Marathi completion, selected mobile widths and keyboard checks | Native-speaker usability, screen-reader/contrast audit and remaining legacy screen translation |
| Operations | Existing permission, upload, backup/restore checks; additive workflow storage | Local backend suite and build | Production retention/deletion policy, infrastructure, capacity, monitoring and deployment-specific restore drill |

**Validated in the field: none of the new capabilities.** Every verification record in this pass uses controlled local or synthetic inputs. The latest detailed counts and known warnings are in `verification.md`.

## Starting and operating

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts/run.py
```

Open http://127.0.0.1:8000. The launcher starts API/web and the separate worker. If source changed, first build the frontend using `npm --prefix apps/web run build` (or the installed pnpm equivalent). On machines where Node is outside PATH, add `C:\Program Files\nodejs` to the current shell PATH. Existing one-click launcher and backup instructions remain in README.

Demo only: use the existing citizen, operator, inspector and admin accounts on the sign-in screen. Never reuse demo credentials or the demo database for real operations.

- Citizen: Report a problem → submit → retain the server-confirmed receipt → My reports → open tracking. A resolved/closed outcome offers **Challenge outcome and reopen**. Explain the continuing problem, submit, and wait for server confirmation. If connection fails, keep the page open and retry the unchanged request. Refresh tracking before deciding to submit anything new.
- Operator/supervisor: Command centre → **Your next actions**. Filter unassigned or overdue work. Open a case, acknowledge, assign a qualified/scoped inspector, and send a public update. Export visible work orders as JSON for a manual handoff; no municipal work-order integration is claimed.
- Inspector: Your next actions shows assigned cases only. Choose inspection, enter safe observations and measurements, and explicitly check site verification only if performed. Classify findings against the inspection record. Record crew/action references in intervention notes, then monitoring and follow-up. Measurements need units, duration and method; leave unknown fields blank.
- Administrator: Administration → Response targets and supervisor. Enter domain, severity, approved hours, team, supervisor account ID, basis and reason. Save. Ensure the supervisor remains authorized for all applicable zones. Review the queue if accounts change. A target is for the next update, not a guaranteed repair time.
- Worker: polls overdue targets and sensor contact states. Repeated polls do not duplicate a state alert or a target escalation. It never resolves a complaint automatically. A stopped worker delays escalation and external-message attempts; HTTP health alone does not certify worker availability.

## Walkthrough A: one complete water investigation

1. Collect dated meter observations with source, units and quality. Review Water analytics and Operations: baseline, supply windows, data gaps and meter condition. A model finding is a suspected issue. Check plausible causes including demand change, tank filling and meter error.
2. Open the detected case, or create a citizen observation and explicitly link the registered asset when supported. Acknowledge and assign a responsible inspector.
3. Record site inspection, measurement method, volume/duration and supply context. A confirmed-leak classification must reference a site-verified water inspection. Classification is a human record, not independent certification.
4. Record intervention, responsible crew and work reference. Move into monitoring.
5. Record follow-up after the latest intervention. Compare equivalent supply/time windows and coverage using existing water operations/group comparisons. Attach the review to the Evidence Passport if appropriate.
6. Operator reviews evidence, records the internal decision and a separate citizen-facing explanation, then resolves. A later explicit human decision may close the case. There is no time-based automatic closure.
7. Export the Evidence Passport and complete the evaluation template below. Changes in observations do not by themselves establish causal savings.

Enforcement boundary: confirmed-leak and false-alert classifications require a linked site-verified inspection. The intervention endpoint also permits emergency action without a prior inspection; it does not thereby establish a confirmed leak. Resolution requires a recorded intervention and later follow-up, plus the separate public explanation. The full ordered pilot sequence above is an operating procedure, not a claim that every earlier step is mandatory at every API endpoint.

## Walkthrough B: inspected false alert, disputed closure

1. An unusual consumption pattern is investigated. The inspector finds scheduled tank filling instead of leakage and records a site-verified inspection.
2. Inspector selects **False alert / issue disproved**, references that inspection and explains the alternatives checked.
3. Operator closes with an explicit public explanation. Uninspected dismissal is rejected.
4. Citizen opens tracking, reads the explanation and challenges it because water remains visible.
5. The server reopens the case for investigation, preserves the previous history, clears the current resolution/classification and resets any configured response target. Repeating the same challenge returns the original acknowledgment.
6. The assigned inspector inspects again. Evidence from before reopening cannot establish the new classification. Any repair route needs new intervention and subsequent follow-up before resolution.

## Water ingestion and simulator

OpenAPI documentation: `/docs`. Admin registers a device with `POST /api/v1/sensors/register`, binding it to one registered water asset and configuring stale/offline minutes. The source is Simulated in demo mode, Live only in a separate non-demo environment on non-synthetic assets. Registration returns a random secret once; only its SHA-256 hash is stored. Store it in a device secret store, never a repository or recording.

Send `POST /api/v1/sensors/{asset_id}/readings` with `Authorization: Bearer <device-secret>` and:

```json
{"readings":[{"id":"unique-device-reading-0001","timestamp":"2026-10-29T10:00:00+05:30","interval_minutes":5,"quantity":12.5,"unit":"L","quality":"valid"}]}
```

- Timestamp is interval start and must include timezone. L and m3 are accepted and stored as L; these are interval volumes, not cumulative meter counts or instantaneous flow. Convert cumulative counters only with verified reset/rollover handling upstream.
- Up to 100 readings per packet; positive interval up to 1,440 minutes; finite nonnegative measurements. Missing is `quantity:null, quality:"missing"`; never substitute zero. Future interval ends beyond five-minute clock tolerance are rejected. Delayed readings are retained with observation and receipt times.
- Same reading ID or asset/timestamp with identical normalized content is a duplicate acknowledgment; conflicting content or overlaps are rejected. The packet is atomic. On 409 concurrent writes, retry the exact payload; conflicting measurement content needs investigation, not endless retry.
- Empty readings list is an authenticated heartbeat. Contact can be reporting while observation data is stale or missing. Recovered-at records return from a stale/offline state; it does not prove sensor accuracy. A disable/enable configuration and key-rotation endpoint support revocation.
- Requires HTTPS for real devices, synchronized clocks, stable IDs, calibration, power/connectivity, provisioning/revocation operations, and a scoped gateway. No physical connection has been validated.

Run the self-contained synthetic demonstration:

```powershell
.\.venv\Scripts\python.exe scripts/simulate_water_sensor.py
```

It creates an isolated database under `.runtime`, uses a simulated clock, and writes `artifacts/verification/sensor-simulation.json`. Phases: normal, unusual consumption input, missing reading, stale contact, offline contact, recovered contact. It exercises the real ingestion/state APIs; the unusual input does not claim validated anomaly detection or a confirmed leak. The test suite separately covers malformed data, duplicate/conflicting packets, secrets, and alert deduplication.

Network Explorer remains a connectivity sandbox. Reachability and route alternatives are not pressure, flow or hydraulic predictions.

## Notification delivery

In-app notifications are persisted with case updates. Settings/Notifications → Email delivery history allows explicit opt-in. No outbound email is attempted for accounts that have not opted in. Configure the worker environment with `CIVIC_SMTP_HOST`, `CIVIC_SMTP_PORT` (default 587), `CIVIC_SMTP_FROM`, and, when required, `CIVIC_SMTP_USER` / `CIVIC_SMTP_PASSWORD`. SMTP uses STARTTLS with certificate validation. These environment values are not browser settings or committed secrets; the launcher does not automatically load `.env` files.

Emails contain a generic bilingual sign-in notice, not complaint descriptions, locations or internal notes. No provider configured means visible failure, never simulated success. Attempts are retained; automatic retries are bounded to three, with five-minute spacing. Failed attempts can be retried by their owner. Provider acceptance is recorded as such; delivery/read confirmation and bounce processing are not implemented. A crash after provider acceptance and before recording it can cause a duplicate generic notice (at-least-once delivery). Live email validation requires a configured provider and verified recipient consent. Tests replace the transport; they send no real messages.

## Pilot evaluation worksheet

Complete per pilot window. Preserve raw measurements and method/version references. Leave unknown outcomes blank.

| Measure | Required evidence / denominator | Result |
|---|---|---|
| Pilot scope | Location, assets, staff, dates, permissions, source provenance | Pending |
| Completeness | Expected intervals, received usable intervals, invalid/missing counts and overlaps | Pending |
| Optional software feed contact availability | Expected reporting periods and recorded contact-state intervals; distinguish heartbeat from measurement quality | Pending |
| Verified issues / false alerts / inconclusive | Counts of site-verified classifications; denominator = investigated alerts, not all alerts | Pending |
| Acknowledge / investigate / resolve time | Submission and first relevant audit timestamps; report median, range and unresolved cases | Pending |
| Repeated reports / reopened cases | Linked report counts, citizen-dispute history, matching criteria | Pending |
| Staff effort | Observed staff minutes and repeated-entry count; collection method and sample size | Pending |
| Water outcome | Matched baseline/follow-up windows, volumes, supply hours, coverage, meter/calibration changes | Pending |
| Cost outcome | Verified tariff, measured quantity basis, actual labour/material costs and missing inputs | Pending |
| Confounders | Seasonality, weather, supply interruption, demand/population changes, other repairs | Pending |
| Citizen experience | Understanding of status, receipt, challenge and resolution; voluntary feedback | Pending |
| Marathi/mobile/accessibility | Native-speaker tasks, keyboard/screen-reader journeys, contrast and low-bandwidth observations | Pending |

Prefer comparable local hour/day and supply-duration windows; explain excluded intervals before looking at outcomes. Report coverage and uncertainty alongside any difference. A before/after difference is observational, not proof that CivicSignal caused savings. Do not publish an accuracy percentage without a defined independently verified sample.

## Municipal pilot checklist and external dependencies

- [ ] Obtain permission, identify a service owner and supervisor, agree on escalation cover and approved targets.
- [ ] Select a small water network, inventory existing software records, verify source/unit/time conventions, configure authorized imports, and keep demo and operational databases separate.
- [ ] Train staff on suspected versus confirmed issues, field evidence, public versus internal text, false alerts and citizen disputes.
- [ ] Test loss of connectivity, slow responses, repeated submissions, device silence and restart recovery before field use.
- [ ] Verify actual email delivery and sender domain; add bounce processing if required.
- [ ] Conduct native Marathi usability sessions and assistive-technology/contrast audits. Automated layout and keyboard tests do not replace these.
- [ ] Establish consent, access review, locally approved retention periods, deletion/anonymization rules, and incident response. No new automatic deletion policy is imposed by this change.
- [ ] Verify backup/restore on the deployment's database and storage. Existing backup tooling remains available; this pass does not certify a production restore drill.
- [ ] Provision hosting/TLS, distributed abuse controls, worker monitoring, capacity tests and an independent security review.
- [ ] Collect the evaluation worksheet with real observations and independent site verification. Hardware is outside scope. Municipal adoption, measured benefits and operational reliability remain unvalidated.

Storage is additive: new response policy, sensor registration and notification outbox use namespaced Configuration rows; challenges use existing Evidence/Audit records. No destructive schema migration or replacement of observations is performed. Roll back application code only after backing up and stopping the new worker. Retain namespaced records and evidence for later recovery; older versions will not process the new workflows and may have weaker closure rules, so rollback is not appropriate while accepting operational complaints.

## Software-only scope update — 31 October 2026

No sensor purchase or physical integration is required. Use CSV imports, citizen reports, synthetic scenarios and the isolated software simulator. Legacy ingestion APIs are optional software-feed interfaces. Hardware terminology in earlier API names is not a hardware dependency. See software-only-handover.md for current acceptance and render-free-deployment.md for hosting. The new photo table is migration 0009; follow its backup/downgrade guidance rather than the earlier schema-only rollback note.
