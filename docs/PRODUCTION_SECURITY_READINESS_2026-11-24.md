# UNO LUCK — Production Security & Private Editor Readiness
**Audit cutoff:** 2026-11-24 WIB  
**Status:** **NO-GO for production/public OPEN/real-value**  
**Audit scope:** read-only repository and Railway metadata; source checkpoint 2026-10-24 and integration/math checkpoint 2026-11-07 22:41 UTC; basic code-review of running CP09 branch and draft PR #34/#35/#36. No penetration test, no secret values, no signed production identity verification.

## Scope and provenance (keep versions separate)
- Repo: `9dbit/uno-luck`, **public**, default `main` at `886a72b0c06627bf5c3099e856a410468c84fbf4`.
- Current accessible Railway project `UNO LUCK` (`14cc881e-e478-406a-bad7-a1c1bb356892`) has **staging only** (`c22194d6-35a2-4297-8eb6-c9f455a27f08`). No Railway production environment exists there.
- `uno-luck-web` staging: commit `c8327f47086d524a43559e297a42bef183d514e4` on `deploy/cp09-uno-runtime-preserved`, health/deploy SUCCESS, sound-only 512 MB persistent volume mounted `/data/uno-luck-audio`. No `UNO_SPIN_DB_PATH` variable and no durable database volume: `app/spin.py` defaults to `/tmp/uno_luck_spin.sqlite3`.
- `uno-game-data-pilot` staging: draft PR #34 commit `da102743ac1d1a91819219eb8b8944dec86a0854`, separate 512 MB `/data/uno-luck` volume, integration variables present, deploy SUCCESS. This is not the public game service, not production.
- `uno-luck-dev08-layout-qa`: QA-only CSS branch `b0d297c9cc6bb0297bbd9c1f02175c6a1a19218f`, no persistent volume. Not a production baseline.
- PR #35 `feat/agency-native-wallet-20261108` `a46fa7b36cc54c9cba60a9361432f0ebe076d746`: **open draft**, linked Playground wallet sandbox test. PR body reports 118 tests and cross-repo UAT. Guest gifts/refills blocked on agency service, sandbox only. Original 195.36% ideal gross return explicitly *not* certified for real-value.
- PR #36 `fix/native-uno-readonly-audio-20261110` `3b73422e8bf69949238b519164ce77f6ef825c4a`: **open draft**, fixes native audio and completed-round timestamp. PR body explicitly requires combined target and dependency qualification; no production certification.
- Integration checkpoint cutoff 7 Nov/8 Nov: final local 50/50 aggregate and separate final-3 17/17; four intentional HOLD, unresolved Final-1 abrupt exit, no power-failure/physical custody, staging/general OPEN/real-value remain NO-GO. No independent production proof. Do not conflate this with an application live deployment.

## Findings / risk register
| ID | Severity | Evidence | Required disposition |
|---|---|---|---|
| P0-01 | BLOCKER | No isolated production environment. Only Railway staging services. | Provision independent production project/environment, credentials, persistent database, storage, keys, access policy, rollback. No shared writable volumes. |
| P0-02 | BLOCKER | `uno-luck-web` has only sound volume. `app/spin.py:database_path()` defaults to `/tmp/uno_luck_spin.sqlite3`; service has no `UNO_SPIN_DB_PATH`. | Introduce durable authoritative wallet database and verify snapshot/restore before any persistent account onboarding. No claim that the running staging ledger persists across rebuild/redeploy. |
| P0-03 | BLOCKER | Checkpoint local original-intent protocol allows 4 HOLD and has unexplained Final-1 abrupt exit; production migration/identity/failover, physical durability not certified. | Resolve HOLD/manual runbook, recovery liveness, cross-host key custody, documented DR and physical failure tests. Keep writer closed. |
| P0-04 | BLOCKER | Draft PR35/PR36 not combined and qualified in an exact provider release candidate. No canonical promoted SHA. | Pin one release candidate with reproducible build/SBOM, integrate provider/native history + audio, re-run ledger/wallet, UI, security, restart/rollback tests against same artifact. |
| P0-05 | BLOCKER for any real-value | Source PR34 agency paytable has 195.36% ideal gross return, with assumptions documented; promotion and actual deployed configs differ. No economic design for real value approved. | Keep **nonpurchasable/nonredeemable demo coins only**. Independent RNG/paytable/auditor and liability stress review for any model change; never dynamically force player outcomes to meet profit target. |
| P1-01 | HIGH | `GET /admin` and static `/assets/admin.html` are openly served; mutable Sound Cloud API uses a shared server token supplied from browser and `sessionStorage` (`sound-studio.js`). This is not individual MFA/RBAC. | Never expose editor on public production origin. Build separate SSO/MFA admin, reviewer/publisher approvals, short-lived secure server session, CSRF protection, immutable audit. No browser-held master key. |
| P1-02 | HIGH | `/api/spin/state` creates new guest accounts; `guard_write` checks `X-UNO-Client` plus cookie and 250ms per-account delay, not distributed IP/device rate limiting; WebSocket ping bypasses action limiter. | Edge bot/WAF/rate limits, quotas and abuse budget; Redis/global limits for API and WS handshakes, abuse monitoring, load/soak. Tests before unpausing admission. |
| P1-03 | HIGH | CP09 `/ws` admits a missing Origin and derives same-origin from request Host; no independently configured strict host allowlist. | Enforce canonical allowed Host/Origin and TLS; inventory WebSocket/API routes, normalize proxy headers; test cross-origin, connection floods, malformed frames. |
| P1-04 | HIGH | Only `.github/workflows/test.yml` on deployed CP09 branch; no specialized SAST, dependency audit, secrets scan, SBOM or signed release/branch protection evidence. Public repo; rulesets API returned `[]`, branch protection not readable through connector (403). | Enforce protected release branch, review + signed artifacts, GitHub CodeQL/bandit/pip-audit, secret scanning, reproducible lockfile, CI policy; verify settings manually. |
| P1-05 | HIGH | SoundCloud publishing is a single shared token; mutable upload/manifest endpoints accept audio, no separate staff approval trail. | Private audio/editor API with individual roles, two-person publish, MIME/content validation, malware/media processing, revision rollback and publish audit. |
| P1-06 | HIGH | Separate integration trust roots and source identities in local sandbox, producer/receiver commitments; PRs independently advanced. | Key rotation, KMS/external custody, role separation, audit timestamps, signed source/receiver ACK and disaster restore without arbitrary credit replay. |
| P2-01 | MEDIUM | Running CP09 response middleware primarily sets cache policy; no comprehensive verified API security header inventory and no independent header scan. PWA audio/CSP are sensitive to changes. | Test CSP at HTTP layer, HSTS after TLS, no-sniff/referrer policy, per-route frame-ancestors; never blanket-block game iframe embeds without checking XDPLAY. |
| P2-02 | MEDIUM | Physical iPhone Safari/PWA acceptance, offline restore, lifecycle and restart tests from older QA are not evidence for the final combined native provider artifact. | Retest iPhone 15 Pro/Pro Max, notch/safe-area, WebKit audio gesture, BGM, animation and resume, wallet/ledger after app suspended and server restart. |
| P2-03 | HIGH, legal/compliance | UNO branding/card motifs and marketing image claim “WIN UP TO x1000”; checkpoint says X1000 is decorative and is not an enabled multiplier. Indonesia PSE/PDP and online gambling classification require counsel review. | Reconcile marketing/disclosure to published paytable, use originality/trademark review, privacy policy/retention, minors/age design, PSE analysis, and seek qualified Indonesian legal review before any public wagering or value-linked credits. |

## Private editor specification (NOT implemented yet)
1. Separate restricted admin host/service behind approved OIDC/Cloudflare Access or equivalent SSO with per-person MFA, no public editor entrypoint.
2. Roles: **viewer** (reports), **editor** (draft audio/UI/rules), **reviewer** (independent validation), **publisher** (execute signed versioned release), **operator** (infra/rollback, not game odds). Enforce on server, not hidden buttons.
3. Never expose `UNO_SOUND_ADMIN_TOKEN` or ledger signing secrets in client JS or browser session/local storage. Use server-side short-lived HttpOnly Secure SameSite cookies with CSRF defense and explicit session revocation.
4. Require dual approval for publishing any sound/rules/economy/wallet/config changes; store diff, version, actor, justification, timestamp, IP/device metadata with retention and immutable audit.
5. Preview isolated from live wallet; approval only promotes reviewed artifact. Private editor cannot create/wipe ledger or reroll a settled game.
6. SoundCloud mixer/cues must preserve existing published revision unless specifically approved and verified; no migration by default.

## Safe implementation in this draft PR
- `app/production_safety.py` determines true production by `RAILWAY_ENVIRONMENT_NAME`, `UNO_DEPLOYMENT_TIER` or `UNO_ENVIRONMENT`.
- Production startup rejects unsafe defaults (missing persistent /data SQLite and sound paths, invalid HTTPS origin allowlist, enabled QA fixtures, public sound master token, wallet commands or public round activation).
- Only production mode returns 404 for legacy `/admin` routes/asset HTML/JS/CSS, 403 for Sound publishing, and 503 for original guest/Orbit round endpoints. It also rejects legacy multiplayer `/ws`.
- Staging/QA behavior, gameplay algorithm, client, wallet ledger, Sound Cloud settings, and published assets remain unchanged.
- This is a **fail-closed safety barrier**; it is NOT a functioning private editor, audited payment system, approved ledger integration, regulatory clearance or permission to open public rounds.
- `tests/test_production_safety.py` covers environment validation, reserved routes, and unchanged staging. `.github/workflows/production-security-gate.yml` runs focused regression tests plus dependency/SAST scans on this candidate.

## Order of work / exit criteria
1. Merge none of the draft PRs without a single reviewed source-of-truth and exact SHA. Reconcile CP09, PR35, PR36, Genesis native contracts and wallet source.
2. Finish database/ledger durability architecture: authoritative source, backups, restore drills, settlement uniqueness, no SQL state split between staging and production. Track DB age/size, WAL safety, no multi-replica SQLite writers.
3. Build private editor SSO/MFA, permission and audit system; disable legacy public publisher on production.
4. Independent security review using OWASP ASVS 5.0.0 and OWASP API Top 10 2023: authN/Z, BOLA/BFLA, CSRF/CORS, XSS, SSRF/media upload, input validation, DoS, supply chain, storage encryption, telemetry/secrets redaction.
5. Run full code/DAST review against authorized isolated test environment, plus dependency/secret scans and representative load/soak. No disruptive stress tests on public services.
6. Complete RNG/paytable and marketing disclosure verification. Virtual-only business model until written legal/commercial decision. Review applicable Indonesian PSE and personal-data rules with counsel.
7. Validate power-loss/restore and signed retry matrix with an isolated central wallet, plus physical iPhone/PWA; test backups across host boundaries.
8. Release board obtains signed go-live approvals: security, platform, game math, legal, operations and owner. Only then create isolated production environment, rotate secrets, seed non-purchasable credits if authorized, progressive canary, rollback rehearsal.
9. Define hard launch SLOs: no unexplained financial discrepancies, zero unreviewed high/critical findings, alerting on 4xx/5xx/latency/event lag, signed settlement proof, daily restore evidence and operational runbooks.

## What this audit did NOT do
- No credential values were read or changed; only Railway variable **names** and service metadata were inspected.
- No active penetration test, live paid wager, user transaction, RNG change, wallet migration, public deployment, current production provision or Sound Cloud publish.
- No claim that GitHub branch protection is disabled: it is **unverified** due connector 403 (rulesets read returned empty).
- No code coverage claim beyond tests that actually run on this PR.
