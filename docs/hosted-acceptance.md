# Hosted acceptance check

`scripts/hosted-acceptance.mjs` checks the deployed non-demo service. It uses HTTPS and an exact same-origin URL. The default mode reads only public endpoints and confirms private routes reject anonymous requests. It prints no passwords, session cookies or CSRF tokens.

## Read-only check

From the repository root:

```powershell
node scripts/hosted-acceptance.mjs --read-only
```

The check covers service health, non-demo mode, public zone metadata, the phone installation URL and QR, and anonymous denial for account/report routes. It reports the number of configured service zones, without publishing their names. Free hosting may take time to wake; a timeout or unavailable service is a failed hosted check, not proof that database records were lost.

## Authenticated check

Use a dedicated test citizen account created through the public registration page. Keep its password out of Git, screenshots and chat. In a temporary PowerShell session:

```powershell
$env:CIVIC_ACCEPTANCE_EMAIL = Read-Host 'Test citizen email'
$secure = Read-Host 'Test citizen password' -AsSecureString
$env:CIVIC_ACCEPTANCE_PASSWORD = [System.Net.NetworkCredential]::new('', $secure).Password
node scripts/hosted-acceptance.mjs --authenticated
```

This signs in, checks the active session and reads only that account's bootstrap and report list. It does not create reports or send photographs. Clear the shell variables when finished:

```powershell
Remove-Item Env:CIVIC_ACCEPTANCE_EMAIL,Env:CIVIC_ACCEPTANCE_PASSWORD -ErrorAction SilentlyContinue
```

## Synthetic report and private image

This mode **permanently creates a clearly labelled synthetic report and one synthetic image** in the hosted database. First, an administrator must create a test service zone in Administration. Use a dedicated citizen test account, then set a stable run ID so reruns use the same submission keys:

```powershell
$env:CIVIC_ACCEPTANCE_RUN_ID = Get-Date -Format yyyyMMddHHmmss
$env:CIVIC_ACCEPTANCE_ALLOW_WRITE = 'yes'
node scripts/hosted-acceptance.mjs --write
```

The script submits one water report with an explicitly synthetic location, uploads the repository's app icon as a test PNG, and verifies the citizen can read the receipt and sanitized JPEG while an anonymous request is denied. Copy the returned report and evidence IDs for a later persistence check. It does not assert an unrelated signed-in citizen is denied, or test a staff decision or worker job; those require separate acceptance journeys. The synthetic report stays in the investigation queue until authorized staff review it.

After a Render restart/redeploy, sign in with the same test citizen account and check persistence:

```powershell
$env:CIVIC_ACCEPTANCE_REPORT_ID = Read-Host 'Report ID from write result'
$env:CIVIC_ACCEPTANCE_EVIDENCE_ID = Read-Host 'Evidence ID from write result'
node scripts/hosted-acceptance.mjs --verify
Remove-Item Env:CIVIC_ACCEPTANCE_EMAIL,Env:CIVIC_ACCEPTANCE_PASSWORD,Env:CIVIC_ACCEPTANCE_ALLOW_WRITE,Env:CIVIC_ACCEPTANCE_RUN_ID,Env:CIVIC_ACCEPTANCE_REPORT_ID,Env:CIVIC_ACCEPTANCE_EVIDENCE_ID -ErrorAction SilentlyContinue
```

The image check uses a non-sensitive generated app icon, never a citizen photo. The script only uses a dedicated account supplied through the current terminal. The full municipal acceptance still needs an authorized administrator/inspector workflow, safe data handling review, backups, phone-device checks and a pilot with permitted water data. No hardware is required.
