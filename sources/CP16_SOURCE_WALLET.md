# CP16: authoritative virtual balances for the isolated UNO pilot

Enabled only by GAMEOPS_WALLET_ENABLED=1 with a dedicated staging-scoped wallet key and the existing persistent round source. The source stream and player HMAC identity match CP15; tokens, raw account IDs and profile PII are never exported. No changes to outcome generation, cards, paytable, frontend or original UNO service.

Source SQLite AFTER INSERT ledger capture is in the same game transaction. Existing accounts receive an explicit opening_snapshot at CP16 cutover; prior history is not invented. New welcomes, daily bonuses, free refills, wager debits and payouts are captured automatically. The welcome account/ledger pair is now atomic. Snapshot reconciliation reads actual accounts, checks the captured per-player chain, counts and a manifest, and refuses a false match.

The source initiates signed requests to /api/v3/source-wallet with separate credentials. HTTP never runs while a source SQLite transaction is open. A signed receipt is required to mark a delivery acknowledged. Permanent source command receipts prevent repeat mutations across retry/restart.

Commands require BOTH the receiver key allowCommands and GAMEOPS_WALLET_COMMANDS_ENABLED=1. The only accepted commands are positive integer virtual credit/debit, scoped to the exact source stream and pseudonymous player. Current ledger revision, deadline, active-round absence, sufficient balance and the original 1,000,000-coin cap are checked. Outcome parameters are never command fields. Writes to accounts, source ledger, event capture and terminal receipt commit together or all roll back.

Rejected commands are terminal, not automatically retried as a new command. A duplicate identical command returns its stored result without moving balance again. A changed payload with the same ID conflicts. Applied results are transmitted only after their ledger events are acknowledged. Receiver acceptance must match a specific ledger sequence and amount before admin labels Applied.

Original CP15 source remains usable. The new public /api/gameops/wallet-status exposes only aggregate pilot health and no balances or player IDs. Wallet export retries with bounded backoff. This first pilot supports integer DEMO_COIN, not bank money, withdrawals, cross-game transfers or KYC. Per-source verification is bounded to 100,000 captured entries and must be capacity-reviewed before production-scale rollout.

Turning off the network wallet flag stops transport and command polling. Once installed, local ledger capture remains for audit continuity. Disable command processing with GAMEOPS_WALLET_COMMANDS_ENABLED=0; never remove or reset the persistent source volume. No source ownership or MFA changes are needed.
