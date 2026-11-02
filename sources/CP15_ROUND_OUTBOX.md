# CP15: isolated UNO staging data pilot

Baseline: c8327f47086d524a43559e297a42bef183d514e4 (the running CP09 UNO staging source). UI, audio, card generation, probabilities and payout rules are unchanged. This branch is intended for a NEW isolated service, not the existing game.

- GAMEOPS_ROUNDS_ENABLED=1 is accepted only with GAMEOPS_ENVIRONMENT=staging and persistent /data/uno-luck/game.sqlite3. Tests may use localhost and a temporary database with CI=true + GAMEOPS_TEST_MODE=1.
- Completed orbit/legacy rounds are enqueued inside the SAME SQLite transaction that commits the round and its ledger effects. No HTTP request occurs in that transaction.
- Outbox delivery stores immutable event body, stable stream/sequence and pseudonymous player references. Failed/unsigned/unacknowledged sends remain pending with bounded backoff. Retrying never reruns a game outcome or moves a balance.
- Observe effective payout = stake + stored net delta, preserving the existing coin cap. A nominal payout displayed by legacy code is not misreported as credited funds.
- Reconciliation reads actual spins since the source cutover, checks every source row has an outbox record, and sends exact count/totals/ordered SHA256 manifest. A signed matching receipt is recorded with watermark/time. Empty is not a verified nonempty feed.
- Existing guest history before cutover is not silently backfilled. No guest names, cookie/session tokens or raw account IDs are exported. Keys/salt are never logged.
- /api/gameops/status returns counts and source/reconciliation health, not credentials or identities. Production game deployment is not changed by this pilot.

Tests: tests/test_gameops_outbox.py covers atomic completion, failure rollback, replay, source-vs-outbox gap detection, effective capped legacy payout, retry, restart and scope restrictions. Existing engine/orbit/spin tests remain required. Cross-system HTTP and PostgreSQL tests run from Playground CP15 against this exact branch revision.
