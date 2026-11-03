"""CP16 staging-only source wallet journal and acknowledged admin commands.

The game remains the balance authority. This adapter never changes cards, odds,
round outcomes or payouts. Raw account IDs/tokens never leave SQLite.
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
import urllib.request
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from . import round_outbox as rounds

PATH = '/api/v3/wallet-sync'
RECEIVER = 'https://playground-admin-production.up.railway.app' + PATH
ZERO = '0' * 64
CAP = 1_000_000
MAX_COMMAND = 10_000
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
_LOCK = threading.Lock()
_READY = set()
router = APIRouter(prefix='/api/gameops', tags=['virtual source wallet'])

def enabled():
    return os.getenv('GAMEOPS_WALLET_ENABLED') == '1'

def commands_enabled():
    return enabled() and os.getenv('GAMEOPS_WALLET_COMMANDS_ENABLED') == '1'

def config():
    c = rounds.config()  # existing staged source stream and persistent path
    key = os.getenv('GAMEOPS_WALLET_KEY_ID', '')
    secret = os.getenv('GAMEOPS_WALLET_SECRET', '')
    endpoint = os.getenv('GAMEOPS_WALLET_RECEIVER', RECEIVER)
    if not rounds.enabled() or not re.fullmatch('[a-z0-9-]{3,60}', key) or not re.fullmatch('[a-f0-9]{64}', secret):
        raise RuntimeError('Wallet link needs a separate staging machine identity and active round stream')
    if endpoint != RECEIVER and not (rounds.is_test() and re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}/api/v3/wallet-sync', endpoint)):
        raise RuntimeError('Unexpected wallet receiver')
    return {**c, 'wallet_key': key, 'wallet_secret': secret, 'wallet_receiver': endpoint}

def utc(t):
    return datetime.fromtimestamp(float(t), timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

def entry_hash(previous, version, entry, reason, delta, before, after, occurred):
    fields = [str(version), str(entry), str(reason), str(delta), str(before), str(after), occurred]
    return hashlib.sha256((previous + '\n' + '\t'.join(fields) + '\n').encode()).hexdigest()

def player_ref(db, account_id):
    values = rounds.meta(db)
    return 'p_' + hmac.new(bytes.fromhex(values['player_salt']),
        ('uno-luck:staging:' + account_id).encode(), hashlib.sha256).hexdigest()

def register_account(db, account_id):
    if not enabled() and not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='gameops_wallet_accounts'").fetchone():
        return
    db.execute('INSERT OR IGNORE INTO gameops_wallet_accounts(account_id,player_ref) VALUES(?,?)',
               (account_id, player_ref(db, account_id)))

def _functions(db):
    db.create_function('wallet_utc', 1, utc, deterministic=True)
    db.create_function('wallet_chain', 8, entry_hash, deterministic=True)

SCHEMA = [
    "CREATE TABLE IF NOT EXISTS gameops_wallet_accounts(account_id TEXT PRIMARY KEY REFERENCES accounts(id),player_ref TEXT NOT NULL UNIQUE)",
    "CREATE TABLE IF NOT EXISTS gameops_wallet_journal(id INTEGER PRIMARY KEY AUTOINCREMENT,account_id TEXT NOT NULL REFERENCES accounts(id),version INTEGER NOT NULL,entry_id TEXT NOT NULL UNIQUE,reason TEXT NOT NULL,delta INTEGER NOT NULL,balance_before INTEGER NOT NULL,balance_after INTEGER NOT NULL,occurred_at TEXT NOT NULL,chain_hash TEXT NOT NULL,UNIQUE(account_id,version))",
    "CREATE INDEX IF NOT EXISTS ix_wallet_journal_account_version ON gameops_wallet_journal(account_id,version)",
    "CREATE TABLE IF NOT EXISTS gameops_wallet_delivery(account_id TEXT PRIMARY KEY REFERENCES accounts(id),ack_version INTEGER NOT NULL DEFAULT 0,last_synced REAL,last_status TEXT,last_error TEXT)",
    "CREATE TABLE IF NOT EXISTS gameops_wallet_commands(id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES accounts(id),request_hash TEXT NOT NULL,status TEXT NOT NULL,code TEXT NOT NULL,version INTEGER NOT NULL,balance INTEGER NOT NULL,entry_id TEXT,created_at REAL NOT NULL,acknowledged_at REAL)",
    "CREATE TABLE IF NOT EXISTS gameops_wallet_requests(id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES accounts(id),client_id TEXT NOT NULL,amount INTEGER NOT NULL,note TEXT NOT NULL,created_at REAL NOT NULL,acknowledged_at REAL,UNIQUE(account_id,client_id))"
]

def ensure_schema(db):
    if not enabled():
        # The journal remains part of source integrity after activation. Turning
        # off the network feature must not break existing capture triggers.
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND name='wallet_capture_ledger'").fetchone():
            _functions(db)
        return
    c = config()
    _functions(db)
    with _LOCK:
        if c['db_path'] in _READY:
            return
        if db.in_transaction:
            raise RuntimeError('Wallet migration must precede balance transactions')
        for sql in SCHEMA:
            db.execute(sql)
        db.execute('BEGIN IMMEDIATE')
        try:
            # A stored checkpoint initializes exactly once. Existing ledger rows
            # are verified from the real game; no invented welcome or adjustment.
            marker = db.execute("SELECT value FROM gameops_source_meta WHERE key='wallet_migrated'").fetchone()
            if marker is None:
                if db.execute('SELECT count(*) FROM gameops_wallet_journal').fetchone()[0]:
                    raise RuntimeError('Unexpected partial wallet migration')
                for account in db.execute('SELECT id,balance FROM accounts').fetchall():
                    register_account(db, account['id'])
                    before, version, chain = 0, 0, ZERO
                    for r in db.execute('SELECT * FROM ledger WHERE account_id=? ORDER BY rowid', (account['id'],)).fetchall():
                        version += 1
                        if before + r['delta'] != r['balance_after'] or not 0 <= r['balance_after'] <= CAP:
                            raise RuntimeError('Source ledger does not reconcile; wallet activation blocked')
                        occurred = utc(r['created_at'])
                        chain = entry_hash(chain, version, r['id'], r['reason'], r['delta'], before, r['balance_after'], occurred)
                        db.execute('INSERT INTO gameops_wallet_journal(account_id,version,entry_id,reason,delta,balance_before,balance_after,occurred_at,chain_hash) VALUES(?,?,?,?,?,?,?,?,?)',
                            (account['id'], version, r['id'], r['reason'], r['delta'], before, r['balance_after'], occurred, chain))
                        before = r['balance_after']
                    if before != account['balance'] or not version:
                        raise RuntimeError('Authoritative account balance lacks matching ledger evidence')
                rounds.put_meta(db, 'wallet_migrated', utc(time.time()))
            db.execute("""CREATE TRIGGER IF NOT EXISTS wallet_validate_ledger BEFORE INSERT ON ledger BEGIN
              SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM gameops_wallet_accounts WHERE account_id=NEW.account_id)
                THEN RAISE(ABORT,'wallet_mapping_missing') END;
              SELECT CASE WHEN NEW.balance_after != COALESCE((SELECT balance_after FROM gameops_wallet_journal WHERE account_id=NEW.account_id ORDER BY version DESC LIMIT 1),0)+NEW.delta
                OR NEW.balance_after<0 OR NEW.balance_after>1000000
                OR NEW.balance_after != (SELECT balance FROM accounts WHERE id=NEW.account_id)
                THEN RAISE(ABORT,'wallet_ledger_balance_mismatch') END;
            END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS wallet_capture_ledger AFTER INSERT ON ledger BEGIN
              INSERT INTO gameops_wallet_journal(account_id,version,entry_id,reason,delta,balance_before,balance_after,occurred_at,chain_hash)
              SELECT NEW.account_id,COALESCE(j.version,0)+1,NEW.id,NEW.reason,NEW.delta,COALESCE(j.balance_after,0),NEW.balance_after,wallet_utc(NEW.created_at),
                wallet_chain(COALESCE(j.chain_hash,'0000000000000000000000000000000000000000000000000000000000000000'),COALESCE(j.version,0)+1,NEW.id,NEW.reason,NEW.delta,COALESCE(j.balance_after,0),NEW.balance_after,wallet_utc(NEW.created_at))
              FROM (SELECT 1) b LEFT JOIN gameops_wallet_journal j ON j.id=(SELECT id FROM gameops_wallet_journal WHERE account_id=NEW.account_id ORDER BY version DESC LIMIT 1);
            END""")
            db.execute("CREATE TRIGGER IF NOT EXISTS wallet_journal_no_update BEFORE UPDATE ON gameops_wallet_journal BEGIN SELECT RAISE(ABORT,'immutable_wallet_journal'); END")
            db.execute("CREATE TRIGGER IF NOT EXISTS wallet_journal_no_delete BEFORE DELETE ON gameops_wallet_journal BEGIN SELECT RAISE(ABORT,'immutable_wallet_journal'); END")
            db.commit()
            _READY.add(c['db_path'])
        except Exception:
            db.rollback()
            raise

def command_hash(c):
    keys = ['id','game','environment','stream_id','player_ref','action','amount','expected_version','expires_at']
    return hashlib.sha256(('gameops.wallet.command.v1\n'+'\n'.join(str(c[k]) for k in keys)).encode()).hexdigest()

def apply_command(db, account_id, c):
    """SQLite atomic/idempotent application. No network during transaction."""
    vals = rounds.meta(db)
    if (not isinstance(c, dict) or not UUID.fullmatch(c.get('id','')) or
        c.get('game') != 'uno-luck' or c.get('environment') != 'staging' or
        c.get('stream_id') != vals['stream_id'] or c.get('player_ref') != player_ref(db, account_id) or
        c.get('action') not in ('credit','debit') or not re.fullmatch(r'[1-9][0-9]{0,4}',str(c.get('amount',''))) or
        int(c['amount'])>MAX_COMMAND or not re.fullmatch(r'[0-9]{1,16}',str(c.get('expected_version',''))) or
        not isinstance(c.get('expires_at'),str) or len(c['expires_at'])>30 or
        not hmac.compare_digest(c.get('request_hash',''),command_hash(c))):
        raise RuntimeError('Command scope/payload invalid')
    expires = datetime.fromisoformat(c['expires_at'].replace('Z','+00:00')).timestamp()
    db.execute('BEGIN IMMEDIATE')
    try:
        prev = db.execute('SELECT * FROM gameops_wallet_commands WHERE id=?',(c['id'],)).fetchone()
        if prev:
            if prev['request_hash'] != c['request_hash'] or prev['account_id'] != account_id:
                raise RuntimeError('Command ID conflict')
            db.commit()
            return dict(prev)
        a = db.execute('SELECT * FROM accounts WHERE id=?',(account_id,)).fetchone()
        j = db.execute('SELECT * FROM gameops_wallet_journal WHERE account_id=? ORDER BY version DESC LIMIT 1',(account_id,)).fetchone()
        if not a or not j or a['balance'] != j['balance_after']:
            raise RuntimeError('Wallet requires source reconciliation')
        delta = int(c['amount']) * (1 if c['action']=='credit' else -1)
        code = 'ok'
        if not commands_enabled():
            code = 'source_commands_disabled'
        elif expires < time.time():
            code = 'command_expired'
        elif expires > time.time()+660:
            code = 'invalid_deadline'
        elif int(c['expected_version']) != j['version']:
            code = 'source_version_conflict'
        elif db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='orbit_rounds'").fetchone() and db.execute('SELECT 1 FROM orbit_rounds WHERE account_id=? AND picked<3',(account_id,)).fetchone():
            code = 'active_round'
        elif a['balance'] + delta < 0:
            code = 'insufficient_balance'
        elif a['balance'] + delta > CAP:
            code = 'balance_cap'
        entry_id = None
        if code == 'ok':
            entry_id = 'admin.' + c['id']
            db.execute('UPDATE accounts SET balance=? WHERE id=?',(a['balance']+delta,account_id))
            db.execute('INSERT INTO ledger(id,account_id,reason,delta,balance_after,created_at) VALUES(?,?,?,?,?,?)',
                (entry_id,account_id,'admin_'+c['action'],delta,a['balance']+delta,time.time()))
        j = db.execute('SELECT * FROM gameops_wallet_journal WHERE account_id=? ORDER BY version DESC LIMIT 1',(account_id,)).fetchone()
        db.execute('INSERT INTO gameops_wallet_commands(id,account_id,request_hash,status,code,version,balance,entry_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
            (c['id'],account_id,c['request_hash'],'applied' if code=='ok' else 'failed',code,j['version'],j['balance_after'],entry_id,time.time()))
        db.commit()
        return dict(db.execute('SELECT * FROM gameops_wallet_commands WHERE id=?',(c['id'],)).fetchone())
    except Exception:
        db.rollback()
        raise

def snapshot(db, account_id):
    db.execute('BEGIN')
    try:
        a = db.execute('SELECT id,balance FROM accounts WHERE id=?',(account_id,)).fetchone()
        mapping = db.execute('SELECT player_ref FROM gameops_wallet_accounts WHERE account_id=?',(account_id,)).fetchone()
        last = db.execute('SELECT * FROM gameops_wallet_journal WHERE account_id=? ORDER BY version DESC LIMIT 1',(account_id,)).fetchone()
        if not a or not last or not mapping or a['balance'] != last['balance_after']:
            raise RuntimeError('Source balance cannot be proved')
        delivery = db.execute('SELECT ack_version FROM gameops_wallet_delivery WHERE account_id=?',(account_id,)).fetchone()
        ack = delivery[0] if delivery else 0
        entries = [dict(x) for x in db.execute('SELECT version,entry_id,reason,delta,balance_before,balance_after,occurred_at,chain_hash FROM gameops_wallet_journal WHERE account_id=? AND version>? ORDER BY version LIMIT 50',(account_id,ack))]
        for x in entries:
            for k in ['version','delta','balance_before','balance_after']: x[k]=str(x[k])
        receipts = [dict(x) for x in db.execute('SELECT id AS command_id,request_hash,status,code,version,balance,entry_id FROM gameops_wallet_commands WHERE account_id=? AND acknowledged_at IS NULL ORDER BY created_at LIMIT 10',(account_id,))]
        for x in receipts:
            x['version']=str(x['version']);x['balance']=str(x['balance'])
        requests = [dict(x) for x in db.execute('SELECT id,amount,note FROM gameops_wallet_requests WHERE account_id=? AND acknowledged_at IS NULL ORDER BY created_at LIMIT 10',(account_id,))]
        for x in requests:x['amount']=str(x['amount'])
        active = bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='orbit_rounds'").fetchone() and db.execute('SELECT 1 FROM orbit_rounds WHERE account_id=? AND picked<3',(account_id,)).fetchone())
        packet={'schema_version':1,'type':'wallet.sync','game':'uno-luck','environment':'staging',
          'stream_id':rounds.meta(db)['stream_id'],'player_ref':mapping['player_ref'],
          'entries':entries,'snapshot':{'version':str(last['version']),'balance':str(a['balance']),
            'manifest':last['chain_hash'],'captured_at':utc(time.time()),'commands_enabled':commands_enabled(),'active_round':active},
          'receipts':receipts,'requests':requests}
        db.commit()
        return packet
    except Exception:
        db.rollback()
        raise

def sign(secret, ts, nonce, raw):
    message='\n'.join(['gameops.wallet.v1','POST',PATH,ts,nonce,hashlib.sha256(raw).hexdigest()])
    return hmac.new(bytes.fromhex(secret),message.encode(),hashlib.sha256).hexdigest()

def exchange(packet):
    c=config();raw=json.dumps(packet,separators=(',',':')).encode()
    ts=str(int(time.time()));nonce=secrets.token_hex(16)
    headers={'Content-Type':'application/json','X-Wallet-Key':c['wallet_key'],'X-Wallet-Time':ts,
        'X-Wallet-Nonce':nonce,'X-Wallet-Signature':sign(c['wallet_secret'],ts,nonce,raw)}
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),rounds.NoRedirect())
    with opener.open(urllib.request.Request(c['wallet_receiver'],data=raw,headers=headers,method='POST'),timeout=8) as response:
        receipt=response.read(32769)
        expected=hmac.new(bytes.fromhex(c['wallet_secret']),('gameops.wallet.receipt.v1\n'+nonce+'\n'+hashlib.sha256(receipt).hexdigest()).encode(),hashlib.sha256).hexdigest()
        if len(receipt)>32768 or not hmac.compare_digest(response.headers.get('X-Wallet-Receipt',''),expected):
            raise RuntimeError('Invalid wallet receipt signature')
        data=json.loads(receipt)
        for k in ['type','game','environment','stream_id','player_ref']:
            if data.get(k)!=packet[k]:raise RuntimeError('Wallet receipt scope mismatch')
        if data.get('accepted') is not True:raise RuntimeError('Wallet not accepted')
        return data

def tick():
    from . import spin
    db=spin.connection()
    try:
        accounts=db.execute('SELECT a.account_id FROM gameops_wallet_accounts a LEFT JOIN gameops_wallet_delivery d ON a.account_id=d.account_id ORDER BY coalesce(d.last_synced,0),a.account_id LIMIT 10').fetchall()
        for row in accounts:
            aid=row['account_id']
            try:
                packet=snapshot(db,aid);answer=exchange(packet)
                ack=int(answer['ack_version'])
                if not 0<=ack<=int(packet['snapshot']['version']):raise RuntimeError('Acknowledgment version invalid')
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO gameops_wallet_delivery(account_id,ack_version,last_synced,last_status) VALUES(?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET ack_version=excluded.ack_version,last_synced=excluded.last_synced,last_status=excluded.last_status,last_error=NULL',
                    (aid,ack,time.time(),answer['reconciliation']))
                for rid in answer.get('request_acks',[]):
                    if UUID.fullmatch(rid):db.execute('UPDATE gameops_wallet_requests SET acknowledged_at=? WHERE account_id=? AND id=?',(time.time(),aid,rid))
                for rid in answer.get('receipt_acks',[]):
                    if UUID.fullmatch(rid):db.execute('UPDATE gameops_wallet_commands SET acknowledged_at=? WHERE account_id=? AND id=?',(time.time(),aid,rid))
                db.commit()
                for command in answer.get('commands',[]):
                    result=apply_command(db,aid,command)
                    print('[gameops-wallet] command_result id='+result['id']+' status='+result['status']+' code='+result['code'],flush=True)
            except Exception as exc:
                if db.in_transaction:db.rollback()
                db.execute('INSERT INTO gameops_wallet_delivery(account_id,last_synced,last_error) VALUES(?,?,?) ON CONFLICT(account_id) DO UPDATE SET last_synced=excluded.last_synced,last_error=excluded.last_error',
                    (aid,time.time(),'sync_or_command_unverified'))
                print('[gameops-wallet] sync_pending_retry',flush=True)
    finally:
        db.close()

class WalletRequest(BaseModel):
    request_id: str = Field(min_length=36,max_length=36)
    amount: int = Field(strict=True,gt=0,le=10000)
    note: str = Field(min_length=5,max_length=300)

@router.post('/wallet-request')
def request_credits(request: Request,payload:WalletRequest):
    if not enabled():raise HTTPException(404,'Source wallet is not enabled')
    from . import spin
    spin.guard_write(request)
    if not UUID.fullmatch(payload.request_id) or type(payload.amount) is not int:
        raise HTTPException(400,'Invalid virtual credit request')
    note=payload.note.strip()
    if len(note)<5 or any(ord(c)<32 for c in note):raise HTTPException(400,'Use a plain-text reason')
    db=spin.connection()
    try:
        db.execute('BEGIN IMMEDIATE');a=spin.account_from_session(request,db)
        old=db.execute('SELECT * FROM gameops_wallet_requests WHERE account_id=? AND client_id=?',(a['id'],payload.request_id)).fetchone()
        if old:
            if old['amount']!=payload.amount or old['note']!=note:raise HTTPException(409,'Request ID conflict')
            db.commit();return {'request_id':old['id'],'state':'submitted_for_review','replay':True,'balance_changed':False}
        recent=db.execute('SELECT count(*) FROM gameops_wallet_requests WHERE account_id=? AND created_at>?',(a['id'],time.time()-3600)).fetchone()[0]
        if recent>=5:raise HTTPException(429,'Too many pending virtual requests; wait for review')
        rid=str(uuid.uuid4())
        db.execute('INSERT INTO gameops_wallet_requests(id,account_id,client_id,amount,note,created_at) VALUES(?,?,?,?,?,?)',
            (rid,a['id'],payload.request_id,payload.amount,note,time.time()))
        db.commit()
        return {'request_id':rid,'state':'submitted_for_review','balance_changed':False}
    except Exception:
        if db.in_transaction:db.rollback()
        raise
    finally:db.close()

@router.get('/wallet-status')
def own_status(request:Request):
    if not enabled():raise HTTPException(404,'Source wallet is not enabled')
    from . import spin
    db=spin.connection()
    try:
        a=spin.account_from_session(request,db)
        last=db.execute('SELECT version,balance_after FROM gameops_wallet_journal WHERE account_id=? ORDER BY version DESC LIMIT 1',(a['id'],)).fetchone()
        d=db.execute('SELECT ack_version,last_status,last_synced FROM gameops_wallet_delivery WHERE account_id=?',(a['id'],)).fetchone()
        return {'balance':a['balance'],'currency':'DEMO_COIN','version':str(last['version']),
            'environment':'staging','sync':dict(d) if d else None,'has_cash_value':False}
    finally:db.close()

def start():
    if not enabled():return lambda:None
    config()
    from . import spin
    db=spin.connection();db.close()
    stop=threading.Event()
    def run():
        while not stop.wait(1 if rounds.is_test() else 5):
            try:tick()
            except Exception:print('[gameops-wallet] worker_error_pending_retry',flush=True)
    threading.Thread(target=run,name='gameops-wallet',daemon=True).start()
    return stop.set
