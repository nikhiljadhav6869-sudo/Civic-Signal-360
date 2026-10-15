# Water operations and field evidence

The **Water → Operations** tab provides supply-window review and zone accounting using recorded interval quantities. It is additional investigation context; it does not change the existing anomaly detector, automatically open or close cases, control supply, or certify leakage.

## Configure a zone

1. Sign in as an administrator and open Water → Operations.
2. Choose an authorized service zone. Expand its configuration.
3. Enter recurring supply windows and legitimate recurring exceptions (for example tank refilling), with a description, weekdays and local start/end times. Choose Asia/Kolkata or UTC explicitly. Overnight windows extend into the following day; use 00:00–24:00 for a whole day.
4. Set the outside-window review threshold in litres/hour. This is an operational review threshold, not a calibrated fault probability.
5. For accounting, choose inlet, outlet and consumption meters and record known parent/child relationships. Each meter can have only one role. Cycles and parent/child double counting on the same accounting side are rejected.
6. Confirm that the selected meters cover the intended accounting boundary only when you have checked it. Enter the reason and assumptions, then save. The server checks administrator permission, zone scope and configuration version and records an audit event. A stale edit must be reloaded before saving.

Operators can review an authorized configuration but cannot edit it. Inspectors use their assigned case evidence workflows; they do not receive the zone operations workspace.

## Review observations

Choose a timezone-aware period of at most 31 days. Review inputs use the displayed workspace timezone preference and convert boundaries to UTC; recurring supply windows use the separately configured schedule timezone. Schedule review classifies recorded intervals as inside a supplied window, outside and above the review threshold, below threshold, straddling a boundary, invalid, or not configured. Straddling intervals are not artificially split into invented measurements. Missing/invalid readings are not replaced with zero.

Zone balance is:

`inlet − outlet − metered consumption − storage change − authorized unmetered volume`

All quantities are litres for the same selected period. A positive storage change means water retained in storage; a negative value means release. Storage change and authorized unmetered use are explicit operator inputs: leave them blank when unknown. If entered, include the source and assumptions. They are not independently verified by the system. A calculated balance requires a confirmed boundary and complete, valid, non-overlapping interval coverage for every selected meter. Otherwise it returns **Unavailable** with reasons. A residual is unexplained water accounting, not a confirmed leak, illegal use or proven saving.

The screen displays the first 100 schedule rows and total status counts. Export the complete JSON review for the full observations, inputs and configuration snapshot. Reviews are not automatically persisted as case evidence. Current configuration does not prove the schedule in force during a historical incident. Meter hierarchy is scoped to this operations configuration; the existing Impact follow-up tool remains a single-meter before/after comparison.

## Domain-specific field observations

In an assigned case, open Evidence Passport → Take action. Record the domain fields, checklist and narrative, then explicitly submit an inspection, intervention or follow-up. Unknown measurements stay blank. Fields include water volume/duration/method, manually measured road dimensions, drain observations, waste collection, lamp state, authorized electrical observations, and general asset condition. Measured water volume requires duration and method. No dimensions are inferred from photos.

The API rejects fields from another domain, invalid numeric values and unsupported inputs. Submitted observations stay with the evidence record and appear in Evidence Passport and its JSON export. Consent-based field drafts retain observations and the exact pending submission for safe retry. The additive `0008_field_observations` migration preserves earlier evidence with an empty observations object.

The water Evidence assistant adds an evidence-gap table for quantities, supply context, inspection and follow-up after the latest intervention. It cites actual source IDs and identifies missing support; it does not invent measurements or decide closure.

## API and verification

- `GET /api/v1/water/zones/{zone_id}/operations`
- `PUT /api/v1/water/zones/{zone_id}/operations` (administrator, versioned)
- `POST /api/v1/water/zones/{zone_id}/review` (authorized operator/administrator)
- `GET /api/v1/cases/{case_id}/field-schema` (authorized case access)

See `tests/test_water_operations.py`, `tests/test_field_observations.py`, `scripts/water-investigation.test.mjs` and `scripts/completion-browser-check.mjs`. The browser acceptance suite uses an isolated demo database and labelled synthetic reports; it is not municipal field validation.
