# CP16 UNO Source Wallet (isolated staging pilot)

Baseline: CP15 pilot 5c060f8562aa98554f9fb064710042f07c658b40. Original UNO service and guest database are not deployment targets.

`GAMEOPS_WALLET_ENABLED=1` enables a separate scoped machine protocol and journal on the existing persistent pilot /data/uno-luck/game.sqlite3. A separate `GAMEOPS_WALLET_KEY_ID` / `GAMEOPS_WALLET_SECRET` is required. `GAMEOPS_WALLET_COMMANDS_ENABLED=1` is an independent explicit gate; default is disabled. New transport endpoint is /api/v3/wallet-sync. CP15 observation keys remain unchanged.

The adapter verifies actual original ledger rows against the source account balance before activation. It copies historical evidence from the pilot ledger, never invents an adjustment to hide a mismatch. New ledger entries are captured by SQLite triggers in the source transaction. Stable pseudonyms reuse the existing per-source salt; raw account IDs, cookie tokens, token hashes and names never leave the source.

A monotonic per-account ledger version and chained manifest protect contiguous receipt. Snapshot includes actual source balance and source timestamp. Completed and incomplete game rounds, bonuses, free refill and administrative credit/debit remain distinguishable in the source ledger.

Signed polling retrieves only commands approved at the authenticated admin with the matching staging source scope. Apply is a short BEGIN IMMEDIATE transaction with durable command ID and request fingerprint. Repeated commands return the same persisted result. Version conflict, expired command, disabled control, active round, insufficient balance and cap overflow cause a signed failure, never a partial change. Applied only follows the matching source ledger proof. Receipt loss is retryable across restart.

Player credit requests use the guest's real HttpOnly session plus the existing client-write guard. They queue for owner review, never grant immediate credits. Requests are limited per account and idempotent. The administrative UI distinguishes pending approval, queued, delivered, applied, failed and rejected. Missing acknowledgment must remain awaiting confirmation.

Card generation, odds, payout tables, original static/audio assets, and rule engine are untouched. No cross-game balances, financial value, withdrawal or KYC claims.

Tests: source unit/integration tests exercise ledger capture and actual SQLite rollback, replay, concurrency, expiry, disabled controls, pending rounds, player requests and refusal to export inconsistent balances. Cross-repository actual HTTP/PostgreSQL tests are maintained by Playground CP16.
