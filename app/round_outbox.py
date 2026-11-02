"""CP15 durable, signed observation outbox. No commands, payouts or wallet sync.

Only enabled on the isolated data pilot. Rows are inserted in the same SQLite
transaction that commits a finished round. Network I/O happens after that commit.
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
import uuid
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request
from .gameops_heartbeat import signed_headers, verify_receipt, NoRedirect, RECEIVER

_LOCK = threading.Lock()
_READY: set[str] = set()

def enabled() -> bool:
    return os.getenv("GAMEOPS_ROUNDS_ENABLED") == "1"

def is_test() -> bool:
    return os.getenv("CI") == "true" and os.getenv("GAMEOPS_TEST_MODE") == "1"

def config() -> dict:
    key, secret = os.getenv("GAMEOPS_BRIDGE_KEY_ID", ""), os.getenv("GAMEOPS_BRIDGE_SECRET", "")
    env = os.getenv("GAMEOPS_ENVIRONMENT", "")
    receiver = os.getenv("GAMEOPS_RECEIVER_URL", RECEIVER)
    db_path = os.getenv("UNO_SPIN_DB_PATH", "/tmp/uno_luck_spin.sqlite3")
    if not (re.fullmatch(r"[a-z0-9-]{3,60}", key) and re.fullmatch(r"[a-f0-9]{64}", secret) and env == "staging"):
        raise RuntimeError("CP15 round export requires a valid staging-scoped key")
    if receiver != RECEIVER and not (is_test() and re.fullmatch(r"http://127\.0\.0\.1:[0-9]{1,5}/api/v2/game-bridge", receiver)):
        raise RuntimeError("Unexpected receiver; redirects and proxy routing are disabled")
    if not is_test() and not Path(db_path).resolve().is_relative_to(Path("/data/uno-luck")):
        raise RuntimeError("Round export requires isolated persistent /data/uno-luck storage")
    return {"key": key, "secret": secret, "environment": env, "receiver": receiver, "db_path": db_path}

def ensure_schema(db: sqlite3.Connection) -> None:
    if not enabled():
        return
    c = config()
    with _LOCK:
        if c["db_path"] in _READY:
            return
        if db.in_transaction:
            raise RuntimeError("Outbox must be initialized before gameplay transactions")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS gameops_source_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS gameops_round_outbox(
          sequence INTEGER PRIMARY KEY AUTOINCREMENT,round_id TEXT NOT NULL UNIQUE,
          payload TEXT NOT NULL,created_at REAL NOT NULL,
          acknowledged_at REAL,receipt_id TEXT,attempts INTEGER NOT NULL DEFAULT 0,
          next_attempt REAL NOT NULL DEFAULT 0,lease_until REAL NOT NULL DEFAULT 0,
          last_error TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_gameops_outbox_pending ON gameops_round_outbox(acknowledged_at,sequence);
        """)
        db.execute("BEGIN IMMEDIATE")
        try:
            if db.execute("SELECT value FROM gameops_source_meta WHERE key='stream_id'").fetchone() is None:
                cutover = db.execute("SELECT coalesce(max(rowid),0) FROM spins").fetchone()[0]
                for k, v in {"stream_id":str(uuid.uuid4()),"player_salt":secrets.token_hex(32),
                             "cutover_rowid":str(cutover),"coverage_started_at":utc(time.time()),
                             "last_reconciliation_status":"not_checked"}.items():
                    db.execute("INSERT INTO gameops_source_meta(key,value) VALUES(?,?)", (k,v))
            db.commit()
        except Exception:
            db.rollback()
            raise
        _READY.add(c["db_path"])

def meta(db) -> dict:
    return dict(db.execute("SELECT key,value FROM gameops_source_meta").fetchall())

def put_meta(db, key, value) -> None:
    db.execute("INSERT INTO gameops_source_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,str(value)))

def utc(stamp: float) -> str:
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def event_for(row, values: dict, sequence: int, environment: str) -> dict:
    stake = int(row["stake"])
    # Spin legacy stores theoretical payout separately; delta reflects the cap.
    # stake + actual net delta is the credited effective payout for BOTH modes.
    payout = stake + int(row["delta"])
    if stake < 0 or payout < 0:
        raise RuntimeError("Invalid source amount; observation refused")
    player = "p_" + hmac.new(bytes.fromhex(values["player_salt"]),
                            ("uno-luck:staging:" + row["account_id"]).encode(), hashlib.sha256).hexdigest()
    return {"schema_version":2,"game":"uno-luck","environment":environment,"type":"round.settled",
            "event_id":"uno.round."+row["id"],"round_id":row["id"],"player_ref":player,
            "currency":"DEMO_COIN","stake":str(stake),"payout":str(payout),
            "occurred_at":utc(row["created_at"]),"stream_id":values["stream_id"],"source_sequence":str(sequence)}

def capture(db: sqlite3.Connection, round_id: str) -> None:
    if not enabled():
        return
    if not db.in_transaction:
        raise RuntimeError("Observation must be in the settlement transaction")
    if db.execute("SELECT 1 FROM gameops_round_outbox WHERE round_id=?",(round_id,)).fetchone():
        return
    row = db.execute("SELECT * FROM spins WHERE id=?", (round_id,)).fetchone()
    if row is None:
        raise RuntimeError("Cannot observe an uncommitted/missing round")
    seq = db.execute("SELECT coalesce(max(sequence),0)+1 FROM gameops_round_outbox").fetchone()[0]
    payload = event_for(row, meta(db), seq, config()["environment"])
    db.execute("INSERT INTO gameops_round_outbox(sequence,round_id,payload,created_at) VALUES(?,?,?,?)",
               (seq,round_id,json.dumps(payload,separators=(",",":")),time.time()))

def connect():
    c = config()
    db = sqlite3.connect(c["db_path"],timeout=8,isolation_level=None)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA busy_timeout=8000")
    return db

def manifest_line(event: dict) -> bytes:
    return ("\t".join([event["source_sequence"],event["event_id"],event["round_id"],event["player_ref"],
                      event["stake"]+".000000000000",event["payout"]+".000000000000",event["occurred_at"]])+"\n").encode()

def source_snapshot(db) -> dict:
    values = meta(db)
    db.execute("BEGIN")
    try:
        through = db.execute("SELECT coalesce(max(sequence),0) FROM gameops_round_outbox").fetchone()[0]
        source = db.execute("SELECT s.*,o.sequence FROM spins s LEFT JOIN gameops_round_outbox o ON o.round_id=s.id WHERE s.rowid>? ORDER BY o.sequence", (int(values["cutover_rowid"]),))
        count,stake,payout=0,0,0
        manifest=hashlib.sha256()
        for row in source:
            count += 1
            if row["sequence"] != count:
                raise RuntimeError("Source/outbox gap or missing capture")
            event=event_for(row,values,count,config()["environment"])
            manifest.update(manifest_line(event))
            stake+=int(event["stake"]);payout+=int(event["payout"])
        if count!=through:
            raise RuntimeError("Unexpected outbox/source mismatch")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"schema_version":2,"game":"uno-luck","environment":config()["environment"],"type":"source.reconcile",
            "stream_id":values["stream_id"],"through_sequence":str(through),"expected_count":str(count),
            "stake":str(stake),"payout":str(payout),"manifest_hash":manifest.hexdigest(),"occurred_at":utc(time.time())}

def exchange(event: dict) -> dict:
    c=config();raw=json.dumps(event,separators=(",",":")).encode()
    headers=signed_headers(c["key"],c["secret"],raw)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    request=urllib.request.Request(c["receiver"],data=raw,headers=headers,method="POST")
    with opener.open(request,timeout=8) as response:
        receipt=response.read(8193)
        if len(receipt)>8192 or not verify_receipt(c["secret"],headers["X-GameOps-Nonce"],receipt,response.headers.get("X-GameOps-Receipt")):
            raise RuntimeError("receipt_signature_invalid")
        data=json.loads(receipt)
        if data.get("accepted") is not True or data.get("type")!=event["type"] or data.get("stream_id")!=event["stream_id"]:
            raise RuntimeError("receipt_scope_invalid")
        if event["type"]=="round.settled" and (data.get("event_id")!=event["event_id"] or data.get("round_id")!=event["round_id"] or data.get("source_sequence")!=event["source_sequence"]):
            raise RuntimeError("receipt_event_invalid")
        if event["type"]=="source.reconcile" and data.get("through_sequence")!=event["through_sequence"]:
            raise RuntimeError("receipt_prefix_invalid")
        return data

def tick() -> None:
    db=connect()
    try:
        for _ in range(20):
            stamp=time.time();db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT * FROM gameops_round_outbox WHERE acknowledged_at IS NULL AND next_attempt<=? AND lease_until<=? ORDER BY sequence LIMIT 1",(stamp,stamp)).fetchone()
            if row is None:
                db.commit();break
            db.execute("UPDATE gameops_round_outbox SET lease_until=?,attempts=attempts+1 WHERE sequence=?",(stamp+30,row["sequence"]))
            db.commit()
            try:
                receipt=exchange(json.loads(row["payload"]))
                db.execute("UPDATE gameops_round_outbox SET acknowledged_at=?,receipt_id=?,lease_until=0,last_error=NULL WHERE sequence=?",(time.time(),str(receipt["id"]),row["sequence"]))
                print("[gameops-outbox] round_acknowledged environment=staging sequence="+str(row["sequence"]),flush=True)
            except Exception as exc:
                error="http_"+str(exc.code) if isinstance(exc,urllib.error.HTTPError) else "receipt_or_network_failure"
                backoff=min(300,2**min(int(row["attempts"])+1,8))
                db.execute("UPDATE gameops_round_outbox SET lease_until=0,next_attempt=?,last_error=? WHERE sequence=?",(time.time()+backoff,error,row["sequence"]))
                print("[gameops-outbox] retry_pending code="+error,flush=True)
                break
        last=float(meta(db).get("last_snapshot_attempt","0"))
        cadence=2 if is_test() else 30
        if time.time()-last>=cadence:
            put_meta(db,"last_snapshot_attempt",time.time())
            try:
                snap=source_snapshot(db);receipt=exchange(snap)
                status=receipt.get("status")
                if status not in ("matched","mismatch","empty"):
                    raise RuntimeError("Unexpected reconciliation receipt")
                put_meta(db,"last_reconciliation_status",status)
                put_meta(db,"last_reconciled_sequence",receipt["through_sequence"])
                put_meta(db,"last_reconciled_at",utc(time.time()))
                print("[gameops-outbox] reconciliation status="+status+" environment=staging count="+receipt["received_count"],flush=True)
            except Exception:
                put_meta(db,"last_reconciliation_status","unverified")
                print("[gameops-outbox] reconciliation_unverified",flush=True)
    finally:
        if db.in_transaction:db.rollback()
        db.close()

def status() -> dict:
    if not enabled():return {"enabled":False}
    db=connect()
    try:
        values=meta(db)
        q=db.execute("SELECT count(*) AS total,coalesce(sum(acknowledged_at IS NOT NULL),0) AS acknowledged,coalesce(sum(last_error IS NOT NULL),0) AS failing FROM gameops_round_outbox").fetchone()
        source_count=db.execute("SELECT count(*) FROM spins WHERE rowid>?",(int(values["cutover_rowid"]),)).fetchone()[0]
        return {"enabled":True,"environment":"staging","stream_id":values["stream_id"],"coverage_started_at":values["coverage_started_at"],
                "source_count":source_count,"queued_total":q["total"],"acknowledged":q["acknowledged"],
                "pending":q["total"]-q["acknowledged"],"retrying":q["failing"],
                "reconciliation":values.get("last_reconciliation_status","not_checked"),
                "reconciled_through":values.get("last_reconciled_sequence","0"),"checked_at":values.get("last_reconciled_at")}
    finally:db.close()

def start() -> callable:
    if not enabled():return lambda:None
    config()
    from . import spin
    db=spin.connection();db.close()
    stop=threading.Event()
    def run():
        while not stop.wait(1 if is_test() else 5):
            try:tick()
            except Exception:print("[gameops-outbox] worker_error_pending_retry",flush=True)
    threading.Thread(target=run,name="gameops-outbox",daemon=True).start()
    return stop.set
