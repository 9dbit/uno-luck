# UNO LUCK: Production Release Security Gate
**Status:** DRAFT | NO-GO | 2026-11-24

This document contains public engineering requirements only. Sensitive service configuration, active environment inventory and detailed vulnerability triage belong in the separately delivered confidential audit, not in this public GitHub repository.

## Engineering control in this draft PR

- Fail closed when deployed in a production environment without explicitly configured persistent data paths and HTTPS origin allowlist.
- Deny the legacy public admin page and public sound publishing endpoints on production.
- Deny original guest/Orbit room admission on production. This PR does not authorize paid or real-value gameplay.
- Preserve staging/QA behavior and gameplay math, promo budgets, Sound Cloud revisions, credits and existing data.
- Require production service owners to validate all checks in an independent, reviewed release candidate.
- Maintain automated regression checks and advisory/static scans in CI.

## Security and private editor requirements

- Separate administrative service/hostname with per-person SSO, MFA, session revocation and least-privilege roles.
- No shared admin master secret stored in browser storage, nor exposed to players.
- Draft, review and publish as distinct permissions. Require independent approval, immutable audit trails, change history, rollback and secret rotation.
- Central authoritative wallet, idempotent signed reserve/settlement, data durability, verified backup/restore and reconciliation evidence.
- Host/Origin protection, abuse/rate limits, API authorization, HTTPS/CSP, logging/alerts, incident response and dependency/secret scanning.
- Third-party security and game-math review, physical mobile/PWA and failure/restore acceptance, privacy/legal review.
- No public launch until written operational approval. A successful CI job is a narrow engineering signal, not an overall compliance or security certification.

## Automated checks

- `tests/test_production_safety.py`: startup validation, private editor and public write-path denial, staging behavior preservation.
- `.github/workflows/production-security-gate.yml`: Python compilation, regression tests, pinned dependency advisory scan and medium/high-severity Bandit scan.
- `requirements.txt`: explicit FastAPI and Starlette security-updated pins for the candidate branch.
- `app/spin.py`: production no longer defaults wallet file storage to a temporary directory; SQL reward category uses explicit statements.

**Boundary:** This code is a candidate patch, not currently deployed. Exact service and vulnerability detail should be handled privately with authorized operators.
