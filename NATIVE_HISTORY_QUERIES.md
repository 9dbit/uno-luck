# Native actor history queries

The native database retains settled rounds and idempotency records. A returning
player's active round, recent history, and counters must be looked up by actor
as unrelated players' retained history grows.

`agency_actor_history` is a non-unique index on
`agency_rounds(actor,state,created_at DESC,payout)`. It supports the existing
settled-history ordering and covers the existing round/win count query.
The actor's count still examines that actor's settled entries; no cached
counter or financial aggregate is introduced.

The active-round and recovery queries use the same `NOT IN ('failed','settled')`
spelling as the existing partial `agency_active` index. SQLite can match the
predicate directly and use that index. Reordering those two literals preserves
the predicate's truth values. The unique index, including its incomplete
settled-round condition, is unchanged.

Startup adds the non-unique index with `IF NOT EXISTS` to new or already bound
databases. It does not rewrite outcomes, requests, sessions, identity bindings,
or identity guards. Index construction needs disk space and a startup write
lock proportional to the retained database; include it in deployment headroom
and startup planning. Ordinary request opens do not rebuild it.

WAL and FULL synchronous durability, committed-intent-before-callback ordering,
status requests, replay handling, worker and callback limits, card generation,
and payout rules are unchanged. No runtime-capacity result is asserted here.

## Validation

`python -m pytest -q tests/test_native_history_queries.py` exercises actual
state and recovery functions with disposable data. The tests capture their SQL,
check real `EXPLAIN QUERY PLAN` output after unrelated history grows from
1,000 to 10,000 rounds, and compare returned rows against independent table
scans. They verify returning-player history and counters, recovery eligibility,
the unchanged unique guard, and repeatable startup migration preserving stored
data, identity rows, and trigger definitions. Assertions do not depend on
elapsed-time ratios. The provider workflow also runs the existing wallet,
concurrency, isolation, disaster-recovery, backup, and math suites.
