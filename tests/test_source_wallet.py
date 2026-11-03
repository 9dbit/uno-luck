"""CP16 isolated source wallet tests. No network, real tokens or deployed data."""
import json
import os
import secrets
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from fastapi import Response
from app import spin, orbit, round_outbox, source_wallet as W


@pytest.fixture
def dbpath(tmp_path, monkeypatch):
    for name, value in {
        'CI': 'true', 'GAMEOPS_TEST_MODE': '1', 'GAMEOPS_ROUNDS_ENABLED': '1',
        'GAMEOPS_WALLET_ENABLED': '1', 'GAMEOPS_WALLET_COMMANDS_ENABLED': '1',
        'GAMEOPS_ENVIRONMENT': 'staging', 'GAMEOPS_BRIDGE_KEY_ID': 'qa-bridge',
        'GAMEOPS_BRIDGE_SECRET': secrets.token_hex(32), 'GAMEOPS_WALLET_KEY_ID': 'qa-wallet',
        'GAMEOPS_WALLET_SECRET': secrets.token_hex(32),
        'GAMEOPS_RECEIVER_URL': 'http://127.0.0.1:1/api/v2/game-bridge',
        'GAMEOPS_WALLET_RECEIVER': 'http://127.0.0.1:1/api/v3/source-wallet',
        'UNO_SPIN_DB_PATH': str(tmp_path/'wallet.sqlite3'),
    }.items():
        monkeypatch.setenv(name, value)
    return str(tmp_path/'wallet.sqlite3')


def account(db):
    request = SimpleNamespace(cookies={}, url=SimpleNamespace(scheme='http'), headers={})
    response = Response()
    return spin.get_account(request, response, db)


def command(db, a, amount='25', action='credit', **changes):
    m = round_outbox.meta(db)
    last = db.execute('SELECT max(player_sequence) FROM gameops_wallet_events WHERE account_id=?', (a['id'],)).fetchone()[0]
    data = {'id': str(uuid.uuid4()), 'game': 'uno-luck', 'environment': 'staging',
            'stream_id': m['stream_id'], 'player_ref': W.ref_for(a['id'], m),
            'action': action, 'amount': amount, 'expected_revision': str(last), 'expires_at': W.utc(time.time()+3600)}
    return {**data, **changes}


def test_welcome_capture_is_atomic_and_matches_round_identity(dbpath):
    db = spin.connection()
    a = account(db)
    rows = db.execute('SELECT * FROM gameops_wallet_events').fetchall()
    assert len(rows) == 1
    assert rows[0]['kind'] == 'welcome'
    assert rows[0]['delta'] == 1000
    assert rows[0]['balance_after'] == a['balance']
    event = W.event_for(rows[0], round_outbox.meta(db))
    assert event['player_ref'] == round_outbox.event_for({'stake': 25, 'delta': 25, 'account_id': a['id'], 'id': 'qa', 'created_at': time.time()}, round_outbox.meta(db), 1, 'staging')['player_ref']
    assert a['id'] not in json.dumps(event)
    assert 'token' not in json.dumps(event)
    snapshot = W.snapshot(db)
    assert snapshot['total_balance'] == '1000'
    assert snapshot['expected_count'] == '1'
    assert snapshot['commands_enabled'] is True
    db.close()


def test_existing_accounts_get_explicit_opening_observation(dbpath, monkeypatch):
    monkeypatch.setenv('GAMEOPS_WALLET_ENABLED', '0')
    db = spin.connection(); a = account(db); db.close()
    monkeypatch.setenv('GAMEOPS_WALLET_ENABLED', '1')
    db = spin.connection()
    row = db.execute('SELECT * FROM gameops_wallet_events').fetchone()
    assert row['kind'] == 'opening_snapshot'
    assert row['balance_after'] == a['balance']
    assert W.snapshot(db)['total_balance'] == '1000'
    db.close()


def test_credit_debit_idempotency_and_stale_source_revision(dbpath):
    db = spin.connection(); a = account(db)
    c = command(db, a, '35'); result = W.apply_command(db, c)
    assert result['status'] == 'applied' and result['balance_after'] == '1035'
    assert W.apply_command(db, c) == result
    assert db.execute('SELECT count(*) FROM ledger WHERE reason="admin_credit"').fetchone()[0] == 1
    with pytest.raises(RuntimeError, match='conflict'):
        W.apply_command(db, {**c, 'amount': '36'})
    stale = W.apply_command(db, {**c, 'id': str(uuid.uuid4())})
    assert stale['status'] == 'rejected' and stale['reason'] == 'stale_revision'
    debit = W.apply_command(db, command(db, a, '35', 'debit'))
    assert debit['balance_after'] == '1000'
    denied = W.apply_command(db, command(db, a, '1001', 'debit'))
    assert denied['reason'] == 'insufficient_balance'
    assert W.snapshot(db)['total_balance'] == '1000'
    db.close()


def test_command_ledger_failure_rolls_back_actual_balance(dbpath):
    db = spin.connection(); a = account(db); c = command(db, a)
    db.execute("CREATE TRIGGER fail_wallet_qa BEFORE INSERT ON ledger WHEN NEW.reason='admin_credit' BEGIN SELECT RAISE(ABORT,'qa_forced_failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        W.apply_command(db, c)
    assert db.execute('SELECT balance FROM accounts WHERE id=?', (a['id'],)).fetchone()[0] == 1000
    assert db.execute('SELECT count(*) FROM gameops_wallet_commands').fetchone()[0] == 0
    db.execute('DROP TRIGGER fail_wallet_qa')
    assert W.apply_command(db, c)['status'] == 'applied'
    db.close()


def test_parallel_commands_cannot_share_one_balance_revision(dbpath):
    db = spin.connection(); a = account(db)
    cmds = [command(db, a, '700', 'debit') for _ in range(2)]; db.close()
    def apply(c):
        d = spin.connection()
        try: return W.apply_command(d, c)
        finally: d.close()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(apply, cmds))
    assert sum(r['status']=='applied' for r in results) == 1
    assert sum(r['reason']=='stale_revision' for r in results) == 1
    db = spin.connection(); assert W.snapshot(db)['total_balance'] == '300'; db.close()


def test_active_round_and_cap_deadline_and_disabled_commands(dbpath, monkeypatch):
    db = orbit.open_db(); a = account(db)
    # Simulate an existing in-flight round. Its wager is untouched by command handling.
    db.execute("INSERT INTO orbit_rounds(id,account_id,start_key,stake,cards_json,picked,combo,tier,rules_version,created_at) VALUES('qa-round',?,'qa-start',25,'[]',1,'NO_MATCH',NULL,2,?)", (a['id'], time.time()))
    result = W.apply_command(db, command(db, a))
    assert result['reason'] == 'active_round'
    db.execute("UPDATE orbit_rounds SET picked=3 WHERE id='qa-round'")
    assert W.apply_command(db, command(db, a, '1000000'))['reason'] == 'balance_limit'
    assert W.apply_command(db, command(db, a, expires_at=W.utc(time.time()-20)))['reason'] == 'expired'
    monkeypatch.setenv('GAMEOPS_WALLET_COMMANDS_ENABLED','0')
    assert W.apply_command(db, command(db,a))['reason'] == 'commands_disabled'
    db.close()


def test_unsigned_or_wrong_scope_commands_never_silently_parse(dbpath):
    db = spin.connection(); a = account(db); c = command(db,a)
    for bad in [{'amount':25},{'amount':'-1'},{'amount':'1.5'},{'environment':'production'},{'stream_id':str(uuid.uuid4())},{'player_ref':a['id']},{'id':'not-a-uuid'}]:
        with pytest.raises(RuntimeError): W.apply_command(db,{**c,**bad})
    assert W.snapshot(db)['total_balance']=='1000'
    db.close()


def test_wallet_gap_detection_blocks_false_reconciliation(dbpath):
    db=spin.connection();a=account(db)
    db.execute('UPDATE accounts SET balance=900 WHERE id=?',(a['id'],))
    with pytest.raises(RuntimeError,match='differs'):
        W.snapshot(db)
    rejected=W.apply_command(db,command(db,a))
    assert rejected['reason']=='source_integrity_error'
    db.close()
