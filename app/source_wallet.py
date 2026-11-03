"""CP16: source-authoritative virtual-credit observations and scoped commands.

Only the isolated staging pilot is supported. Existing outcomes are never changed.
SQLite ledger capture is atomic; HTTP always occurs after a commit. Opening
snapshots declare the cutover instead of inventing pre-cutover transaction history.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
import urllib.request
from .gameops_heartbeat import NoRedirect
from . import round_outbox

PATH = "/api/v3/source-wallet"
RECEIVER = "https://playground-admin-production.up.railway.app" + PATH
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", re.I)
PLAYER = re.compile(r"p_[0-9a-f]{64}")
_LOCK = threading.RLock()
_READY: set[str] = set()
KINDS = {"welcome", "daily", "free_refill", "orbit_stake", "orbit_payout", "admin_credit", "admin_debit", "opening_snapshot", "spin_win", "spin_loss"}
CAP = 1_000_000


def enabled() -> bool:
    return os.getenv("GAMEOPS_WALLET_ENABLED") == "1"


def config() -> dict:
    base = round_outbox.config()
    key, secret = os.getenv("GAMEOPS_WALLET_KEY_ID", ""), os.getenv("GAMEOPS_WALLET_SECRET", "")
    receiver = os.getenv("GAMEOPS_WALLET_RECEIVER", RECEIVER)
    if not (re.fullmatch(r"[a-z0-9-]{3,60}", key) and re.fullmatch(r"[0-9a-f]{64}", secret)):
        raise RuntimeError("Invalid staging wallet key configuration")
    if not round_outbox.enabled():
        raise RuntimeError("Wallet observations require persistent source stream identity")
    if receiver != RECEIVER and not (round_outbox.is_test() and re.fullmatch(r"http://127\.0\.0\.1:[0-9]{1,5}" + PATH, receiver)):
        raise RuntimeError("Unexpected wallet receiver")
    return {**base, "key": key, "secret": secret, "receiver": receiver,
            "commands": os.getenv("GAMEOPS_WALLET_COMMANDS_ENABLED") == "1"}


def utc(stamp: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if stamp is None else stamp, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ref_for(account_id: str, values: dict) -> str:
    # Identical identity derivation to CP15 round events, never the guest token.
    return "p_" + hmac.new(bytes.fromhex(values["player_salt"]),
                            ("uno-luck:staging:" + account_id).encode(), hashlib.sha256).hexdigest()


def ensure_schema(db: sqlite3.Connection) -> None:
    if not enabled():
        return
    c = config()
    with _LOCK:
        if c["db_path"] in _READY:
            return
        if db.in_transaction:
            raise RuntimeError("Wallet schema must initialize outside gameplay transactions")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS gameops_wallet_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS gameops_wallet_events(
          sequence INTEGER PRIMARY KEY AUTOINCREMENT,account_id TEXT NOT NULL,
          player_sequence INTEGER NOT NULL,ledger_id TEXT NOT NULL UNIQUE,
          kind TEXT NOT NULL,delta INTEGER NOT NULL,balance_after INTEGER NOT NULL,
          created_at REAL NOT NULL,command_id TEXT,
          acknowledged_at REAL,UNIQUE(account_id,player_sequence));
        CREATE INDEX IF NOT EXISTS ix_wallet_account_sequence ON gameops_wallet_events(account_id,player_sequence DESC);
        CREATE TABLE IF NOT EXISTS gameops_wallet_commands(
          id TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,payload TEXT NOT NULL,
          result TEXT NOT NULL,reported_at REAL,created_at REAL NOT NULL);
        """)
        db.execute("BEGIN IMMEDIATE")
        try:
            exists = db.execute("SELECT value FROM gameops_wallet_meta WHERE key='coverage_started_at'").fetchone()
            if exists is None:
                started = utc()
                values = round_outbox.meta(db)
                # Explicit initial observation, not an invented bonus or settlement.
                for a in db.execute("SELECT id,balance FROM accounts ORDER BY id").fetchall():
                    db.execute("INSERT INTO gameops_wallet_events(account_id,player_sequence,ledger_id,kind,delta,balance_after,created_at) VALUES(?,1,?,'opening_snapshot',?,?,?)",
                               (a["id"], "opening:" + a["id"], int(a["balance"]), int(a["balance"]), time.time()))
                put(db, "coverage_started_at", started)
                put(db, "source_stream_id", values["stream_id"])
                put(db, "reconciliation", "not_checked")
            # Fail closed if a different data-source namespace was substituted.
            if get_meta(db)["source_stream_id"] != round_outbox.meta(db)["stream_id"]:
                raise RuntimeError("Source stream identity changed")
            db.execute("""CREATE TRIGGER IF NOT EXISTS gameops_wallet_capture
                AFTER INSERT ON ledger BEGIN
                SELECT CASE WHEN NEW.balance_after != (SELECT balance FROM accounts WHERE id=NEW.account_id)
                  THEN RAISE(ABORT,'source_wallet_account_mismatch') END;
                SELECT CASE WHEN NEW.balance_after != NEW.delta + COALESCE(
                  (SELECT balance_after FROM gameops_wallet_events WHERE account_id=NEW.account_id ORDER BY player_sequence DESC LIMIT 1),0)
                  THEN RAISE(ABORT,'source_wallet_ledger_gap') END;
                INSERT INTO gameops_wallet_events(account_id,player_sequence,ledger_id,kind,delta,balance_after,created_at,command_id)
                VALUES(NEW.account_id,COALESCE((SELECT max(player_sequence) FROM gameops_wallet_events WHERE account_id=NEW.account_id),0)+1,
                  NEW.id,CASE NEW.reason WHEN 'spin:COLOR_MATCH' THEN 'spin_win' WHEN 'spin:NO_MATCH' THEN 'spin_loss' ELSE NEW.reason END,
                  NEW.delta,NEW.balance_after,NEW.created_at,
                  CASE WHEN NEW.reason IN ('admin_credit','admin_debit') AND substr(NEW.id,1,3)='wc_' THEN substr(NEW.id,4) ELSE NULL END);
                END""")
            db.commit()
        except Exception:
            db.rollback()
            raise
        _READY.add(c["db_path"])


def get_meta(db) -> dict:
    return dict(db.execute("SELECT key,value FROM gameops_wallet_meta").fetchall())


def put(db, key, value) -> None:
    db.execute("INSERT INTO gameops_wallet_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def event_for(row, values) -> dict:
    if row["kind"] not in KINDS:
        raise RuntimeError("Unknown source ledger reason")
    ledger_ref = "l_" + hmac.new(bytes.fromhex(values["player_salt"]), ("ledger:" + row["ledger_id"]).encode(), hashlib.sha256).hexdigest()
    return {"sequence": str(row["sequence"]), "player_sequence": str(row["player_sequence"]),
            "player_ref": ref_for(row["account_id"], values), "ledger_ref": ledger_ref,
            "kind": row["kind"], "delta": str(row["delta"]), "balance_after": str(row["balance_after"]),
            "occurred_at": utc(float(row["created_at"])), "command_id": row["command_id"]}


def manifest_line(e: dict) -> bytes:
    return ("\t".join(e[k] if e[k] is not None else "" for k in
             ("sequence", "player_sequence", "player_ref", "ledger_ref", "kind", "delta", "balance_after", "occurred_at", "command_id")) + "\n").encode()


def envelope(db, kind: str, **fields) -> dict:
    return {"schema_version": 1, "game": "uno-luck", "environment": "staging", "stream_id": get_meta(db)["source_stream_id"],
            "type": kind, **fields}


def snapshot(db) -> dict:
    db.execute("BEGIN")
    try:
        values = round_outbox.meta(db)
        manifest, seen, through = hashlib.sha256(), {}, 0
        for row in db.execute("SELECT * FROM gameops_wallet_events ORDER BY sequence"):
            e = event_for(row, values)
            if int(e["sequence"]) != through + 1:
                raise RuntimeError("Wallet source sequence gap")
            prior = seen.get(e["player_ref"], {"balance": 0, "revision": 0})
            if int(e["player_sequence"]) != prior["revision"] + 1 or prior["balance"] + int(e["delta"]) != int(e["balance_after"]):
                raise RuntimeError("Wallet source player chain mismatch")
            seen[e["player_ref"]] = {"balance": int(e["balance_after"]), "revision": int(e["player_sequence"])}
            through += 1
            manifest.update(manifest_line(e))
        balance_hash = hashlib.sha256()
        source_balances = []
        total = 0
        for a in db.execute("SELECT id,balance FROM accounts"):
            ref = ref_for(a["id"], values)
            v = seen.get(ref)
            if not v or v["balance"] != a["balance"]:
                raise RuntimeError("Actual game balance differs from captured ledger")
            total += int(a["balance"])
            source_balances.append((ref, int(a["balance"]), v["revision"]))
        if len(source_balances) != len(seen):
            raise RuntimeError("Wallet source account set mismatch")
        for ref, balance, revision in sorted(source_balances):
            balance_hash.update((ref + "\t" + str(balance) + "\t" + str(revision) + "\n").encode())
        result = envelope(db, "wallet.reconcile", through_sequence=str(through), expected_count=str(through),
                          total_balance=str(total), player_count=str(len(seen)), manifest_hash=manifest.hexdigest(),
                          balances_hash=balance_hash.hexdigest(), checked_at=utc(),
                          coverage_started_at=get_meta(db)["coverage_started_at"], commands_enabled=config()["commands"])
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def signed_headers(c, raw: bytes) -> dict:
    nonce, ts = secrets.token_hex(16), str(int(time.time()))
    text = "\n".join(["gameops.wallet.v1", "POST", PATH, ts, nonce, hashlib.sha256(raw).hexdigest()])
    mac = hmac.new(bytes.fromhex(c["secret"]), text.encode(), hashlib.sha256).hexdigest()
    return {"Content-Type": "application/json", "X-Wallet-Key": c["key"], "X-Wallet-Timestamp": ts,
            "X-Wallet-Nonce": nonce, "X-Wallet-Signature": mac}


def exchange(payload: dict) -> dict:
    c = config()
    raw = json.dumps(payload, separators=(",", ":")).encode()
    headers = signed_headers(c, raw)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    req = urllib.request.Request(c["receiver"], data=raw, headers=headers, method="POST")
    with opener.open(req, timeout=8) as response:
        raw_reply = response.read(65537)
        if len(raw_reply) > 65536:
            raise RuntimeError("Oversized wallet receipt")
        message = "\n".join(["gameops.wallet.receipt.v1", headers["X-Wallet-Nonce"], hashlib.sha256(raw_reply).hexdigest()])
        expected = hmac.new(bytes.fromhex(c["secret"]), message.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, response.headers.get("X-Wallet-Receipt", "")):
            raise RuntimeError("Unverified wallet receipt")
        data = json.loads(raw_reply)
        if (data.get("accepted") is not True or data.get("type") != payload["type"] or
                data.get("stream_id") != payload["stream_id"] or data.get("game") != "uno-luck" or data.get("environment") != "staging"):
            raise RuntimeError("Wallet receipt scope mismatch")
        return data


def canonical_command(c: dict) -> str:
    return json.dumps(c, sort_keys=True, separators=(",", ":"))


def apply_command(db, c: dict) -> dict:
    """Called only after a signed poll response. Replays never mutate twice."""
    expected_fields = {"id", "player_ref", "action", "amount", "expected_revision", "expires_at", "stream_id", "game", "environment"}
    if (not isinstance(c, dict) or set(c) != expected_fields or not UUID.fullmatch(c.get("id", "")) or
        not PLAYER.fullmatch(c.get("player_ref", "")) or c.get("action") not in ("credit", "debit") or
        not isinstance(c.get("amount"), str) or not re.fullmatch(r"[1-9][0-9]{0,6}", c["amount"]) or not 1 <= int(c["amount"]) <= CAP or
        not isinstance(c.get("expected_revision"), str) or not re.fullmatch(r"[1-9][0-9]{0,14}", c["expected_revision"]) or
        c.get("game") != "uno-luck" or c.get("environment") != "staging" or c.get("stream_id") != get_meta(db)["source_stream_id"]):
        raise RuntimeError("Invalid wallet command")
    try:
        expires = datetime.fromisoformat(c["expires_at"].replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError("Invalid command deadline")
    encoded = canonical_command(c)
    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
    db.execute("BEGIN IMMEDIATE")
    try:
        prior = db.execute("SELECT payload_hash,result FROM gameops_wallet_commands WHERE id=?", (c["id"],)).fetchone()
        if prior:
            if prior["payload_hash"] != fingerprint:
                raise RuntimeError("Command ID content conflict")
            db.commit()
            return json.loads(prior["result"])
        values = round_outbox.meta(db)
        found = [a for a in db.execute("SELECT id,balance FROM accounts").fetchall() if ref_for(a["id"], values) == c["player_ref"]]
        error = None
        if expires < time.time():
            error = "expired"
        elif not config()["commands"]:
            error = "commands_disabled"
        elif len(found) != 1:
            error = "player_not_found"
        account = found[0] if len(found) == 1 else None
        last = db.execute("SELECT player_sequence,balance_after FROM gameops_wallet_events WHERE account_id=? ORDER BY player_sequence DESC LIMIT 1", (account["id"],)).fetchone() if account else None
        if not error and (not last or last["balance_after"] != account["balance"]):
            error = "source_integrity_error"
        if not error and last["player_sequence"] != int(c["expected_revision"]):
            error = "stale_revision"
        if not error and db.execute("SELECT 1 FROM sqlite_master WHERE name='orbit_rounds'").fetchone():
            if db.execute("SELECT 1 FROM orbit_rounds WHERE account_id=? AND picked<3", (account["id"],)).fetchone():
                error = "active_round"
        amount = int(c["amount"])
        delta = amount if c["action"] == "credit" else -amount
        if not error and account["balance"] + delta < 0:
            error = "insufficient_balance"
        if not error and account["balance"] + delta > CAP:
            error = "balance_limit"
        if error:
            result = {"id": c["id"], "status": "rejected", "reason": error, "ledger_sequence": None,
                      "player_revision": str(last["player_sequence"]) if last else None,
                      "balance_after": str(account["balance"]) if account else None}
        else:
            after = account["balance"] + delta
            db.execute("UPDATE accounts SET balance=? WHERE id=?", (after, account["id"]))
            db.execute("INSERT INTO ledger(id,account_id,reason,delta,balance_after,created_at) VALUES(?,?,?,?,?,?)",
                       ("wc_" + c["id"], account["id"], "admin_" + c["action"], delta, after, time.time()))
            entry = db.execute("SELECT sequence,player_sequence FROM gameops_wallet_events WHERE command_id=?", (c["id"],)).fetchone()
            if not entry:
                raise RuntimeError("Command ledger capture failed")
            result = {"id": c["id"], "status": "applied", "reason": None, "ledger_sequence": str(entry["sequence"]),
                      "player_revision": str(entry["player_sequence"]), "balance_after": str(after)}
        db.execute("INSERT INTO gameops_wallet_commands(id,payload_hash,payload,result,created_at) VALUES(?,?,?,?,?)",
                   (c["id"], fingerprint, encoded, json.dumps(result, separators=(",", ":")), time.time()))
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def tick() -> None:
    db = round_outbox.connect()
    try:
        ensure_schema(db)
        values = round_outbox.meta(db)
        for _ in range(5):
            rows = db.execute("SELECT * FROM gameops_wallet_events WHERE acknowledged_at IS NULL ORDER BY sequence LIMIT 50").fetchall()
            if not rows:
                break
            payload = envelope(db, "wallet.events", events=[event_for(r, values) for r in rows])
            ack = exchange(payload)
            if ack.get("through_sequence") != str(rows[-1]["sequence"]):
                raise RuntimeError("Invalid event acknowledgment watermark")
            db.execute("BEGIN IMMEDIATE")
            try:
                db.executemany("UPDATE gameops_wallet_events SET acknowledged_at=? WHERE sequence=?", [(time.time(), r["sequence"]) for r in rows])
                db.commit()
            except Exception:
                db.rollback()
                raise
        # Report terminal commands only after their ledger rows have been acknowledged.
        for r in db.execute("SELECT * FROM gameops_wallet_commands WHERE reported_at IS NULL ORDER BY created_at LIMIT 10").fetchall():
            result = json.loads(r["result"])
            if result["ledger_sequence"] is not None:
                entry = db.execute("SELECT acknowledged_at FROM gameops_wallet_events WHERE sequence=?", (int(result["ledger_sequence"]),)).fetchone()
                if not entry or entry[0] is None:
                    continue
            ack = exchange(envelope(db, "wallet.result", result=result))
            if ack.get("command_id") != r["id"] or ack.get("status") != result["status"]:
                raise RuntimeError("Invalid command acknowledgment")
            db.execute("UPDATE gameops_wallet_commands SET reported_at=? WHERE id=?", (time.time(), r["id"]))
            print("[source-wallet] command_result_acknowledged status=" + result["status"], flush=True)
        snap = snapshot(db)
        ack = exchange(snap)
        if ack.get("through_sequence") != snap["through_sequence"] or ack.get("status") not in ("matched", "mismatch", "empty"):
            raise RuntimeError("Invalid wallet reconciliation acknowledgment")
        put(db, "reconciliation", ack["status"])
        put(db, "checked_at", utc())
        put(db, "through_sequence", ack["through_sequence"])
        if config()["commands"]:
            poll = exchange(envelope(db, "wallet.poll"))
            commands = poll.get("commands", [])
            if not isinstance(commands, list) or len(commands) > 10:
                raise RuntimeError("Invalid command batch")
            for command in commands:
                apply_command(db, command)
    finally:
        if db.in_transaction:
            db.rollback()
        db.close()


def status() -> dict:
    if not enabled():
        return {"enabled": False}
    db = round_outbox.connect()
    try:
        m = get_meta(db)
        q = db.execute("SELECT count(*) AS n,coalesce(sum(acknowledged_at IS NULL),0) AS pending FROM gameops_wallet_events").fetchone()
        commands = db.execute("SELECT count(*) AS n,coalesce(sum(reported_at IS NULL),0) AS pending FROM gameops_wallet_commands").fetchone()
        return {"enabled": True, "environment": "staging", "commands_enabled": config()["commands"],
                "coverage_started_at": m.get("coverage_started_at"), "source_events": q["n"], "pending_events": q["pending"],
                "commands_processed": commands["n"], "pending_results": commands["pending"], "reconciliation": m.get("reconciliation"),
                "checked_at": m.get("checked_at"), "through_sequence": m.get("through_sequence"),
                "note": "Virtual source credits only; no personal identity or cash value."}
    finally:
        db.close()


def start() -> callable:
    if not enabled():
        return lambda: None
    config()
    from . import spin
    db = spin.connection()
    db.close()
    stop = threading.Event()
    def run():
        failures = 0
        while not stop.wait((1 if round_outbox.is_test() else 5) if failures == 0 else min(60, 2 ** min(failures, 6))):
            try:
                tick()
                failures = 0
            except Exception:
                failures += 1
                print("[source-wallet] sync_pending_retry", flush=True)
    threading.Thread(target=run, name="source-wallet", daemon=True).start()
    return stop.set
