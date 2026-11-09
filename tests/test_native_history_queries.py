"""Returning-player history stays scoped without changing stored outcomes."""
import json
import sqlite3
import time

import pytest
from fastapi import Request, Response
from app import agency, orbit


@pytest.fixture
def native(tmp_path, monkeypatch):
    path = tmp_path / 'native.sqlite'
    for key in ('RAILWAY_PROJECT_ID', 'RAILWAY_SERVICE_ID', 'RAILWAY_DEPLOYMENT_ID',
                'RAILWAY_VOLUME_MOUNT_PATH', 'ENGINE_RESTORE_OBJECT_KEY', 'ENGINE_RESTORE_OBJECT'):
        monkeypatch.delenv(key, raising=False)
    for key, value in {'AGENCY_WALLET_MODE': 'sandbox', 'AGENCY_ENVIRONMENT': 'preproduction',
                       'AGENCY_DEPLOYMENT_ID': 'uno-history-test',
                       'AGENCY_CORE_DEPLOYMENT_ID': 'core-history-test',
                       'UNO_AGENCY_DB_PATH': str(path), 'AGENCY_STUDIO_SYNC': '0',
                       'ENGINE_BACKUP_ENABLED': 'false'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(agency, 'wallet', lambda: object())
    def remote(action, payload):
        assert action == 'status', 'History reads must not mutate a wallet'
        return {'balance': '1000000', 'reserved': '0'}
    monkeypatch.setattr(agency, 'remote', remote)
    agency.validate_config()
    db = agency.db_open()
    session = {'tenant_id': 'history-test', 'player_id': 'returning', 'session_id': 'returning-session',
               'coin_scale': 0, 'game': 'uno-luck', 'provider': 'soft-tech',
               'environment': 'preproduction', 'deployment_id': 'core-history-test'}
    cookie = 'a' * 64
    db.execute('INSERT INTO agency_launches VALUES(?,?,?,?,?)',
               ('synthetic-token', 'synthetic-redemption', agency.sha(cookie), json.dumps(session), time.time()))
    request = Request({'type': 'http', 'method': 'GET', 'path': '/api/agency/state',
                       'headers': [(b'cookie', (agency.COOKIE + '=' + cookie).encode())]})
    yield db, session, request, path
    db.close()


def insert_round(db, session, rid, actor, *, state='settled', picked=3, created_at=1, win=False):
    cards = [{'color': 'red', 'face': str(i)} for i in (1, 2, 3)] if win else [
        {'color': color, 'face': '1'} for color in ('red', 'green', 'blue')]
    tier = orbit.classify_rank(cards)
    payout = 25 * orbit.CELEBRATIONS[tier]['multiplier'] if tier else 0
    db.execute('''INSERT INTO agency_rounds
        (id,actor,session_json,stake,cards_json,combo,tier,payout,picked,state,central_id,created_at,finished_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (rid, actor, json.dumps(session), 25, json.dumps(cards), 'COLOR_MATCH' if tier else 'NO_MATCH',
         tier, payout, picked, state, 'central-' + rid, created_at, created_at + 1 if state == 'settled' else None))


def explain(db, sql):
    return [row[3] for row in db.execute('EXPLAIN QUERY PLAN ' + sql)]


def test_returning_actor_state_and_results_with_growing_unrelated_history(native, monkeypatch):
    db, session, request, _ = native
    actor = 'history-test:returning'
    for i in range(20):
        insert_round(db, session, 'owned-' + str(i), actor, created_at=100 + i, win=i % 2 == 0)
    insert_round(db, session, 'active-owned', actor, state='reserved', picked=1, created_at=time.time())
    original_open = agency.db_open
    statements = []
    def observed_open(**kwargs):
        connection = original_open(**kwargs)
        connection.set_trace_callback(statements.append)
        return connection
    monkeypatch.setattr(agency, 'db_open', observed_open)
    prior_snapshot = None
    previous = 0
    for history in (1000, 10000):
        db.execute('BEGIN IMMEDIATE')
        for i in range(previous, history):
            insert_round(db, session, 'unrelated-' + str(i), 'other:' + str(i % 300), created_at=i)
        db.commit(); previous = history; statements.clear()
        snapshot = agency.state(request, Response())
        assert snapshot['round']['id'] == 'active-owned'
        assert snapshot['account']['spins'] == 20 and snapshot['account']['wins'] == 10
        assert [row['id'] for row in snapshot['recent']] == ['owned-' + str(i) for i in range(19, 11, -1)]
        if prior_snapshot is not None:
            assert snapshot == prior_snapshot
        prior_snapshot = snapshot
        actual = {name: next(sql for sql in statements if 'FROM agency_rounds WHERE actor=' in sql and token in sql)
                  for name, token in (('active', 'state NOT IN'), ('history', 'ORDER BY created_at DESC'), ('count', 'count(*)'))}
        for name, sql in actual.items():
            plan = explain(db, sql)
            expected_index = 'agency_active' if name == 'active' else 'agency_actor_history'
            assert any('SEARCH agency_rounds' in step and expected_index in step for step in plan), plan
            assert not any('SCAN agency_rounds' in step or 'TEMP B-TREE' in step for step in plan), plan
            if name == 'count':
                assert any('COVERING INDEX' in step for step in plan), plan
            # Independent table scan, including the previous NOT IN spelling.
            reference = sql.replace('FROM agency_rounds', 'FROM agency_rounds NOT INDEXED').replace(
                "NOT IN ('failed','settled')", "NOT IN ('settled','failed')")
            assert [tuple(row) for row in db.execute(sql)] == [tuple(row) for row in db.execute(reference)]


def test_recovery_uses_existing_open_round_guard_and_same_eligible_rows(native, monkeypatch):
    db, session, _, _ = native
    old = time.time() - agency.DEADLINE - 30
    db.execute('BEGIN IMMEDIATE')
    for i, state in enumerate(('intent', 'reserved', 'settling', 'failed', 'settled')):
        insert_round(db, session, 'old-' + state, 'actor:' + str(i), state=state,
                     picked=3 if state == 'settled' else 1, created_at=old)
    insert_round(db, session, 'fresh', 'actor:fresh', state='intent', picked=0, created_at=time.time())
    for i in range(2000):
        insert_round(db, session, 'closed-' + str(i), 'closed:' + str(i), created_at=old)
    db.commit()
    statements, advanced = [], []
    original_open = agency.db_open
    def observed_open(**kwargs):
        connection = original_open(**kwargs); connection.set_trace_callback(statements.append); return connection
    monkeypatch.setattr(agency, 'db_open', observed_open)
    monkeypatch.setattr(agency, 'advance', lambda connection, rid: advanced.append(rid))
    agency.recover_due()
    sql = next(sql for sql in statements if sql.startswith('SELECT id FROM agency_rounds'))
    plan = explain(db, sql)
    assert any('USING INDEX agency_active' in step for step in plan), plan
    assert not any(step == 'SCAN agency_rounds' for step in plan), plan
    assert set(advanced) == {'old-intent', 'old-reserved', 'old-settling'}
    reference = sql.replace('FROM agency_rounds', 'FROM agency_rounds NOT INDEXED').replace(
        "NOT IN ('failed','settled')", "NOT IN ('settled','failed')")
    assert set(advanced) == {row[0] for row in db.execute(reference)}


@pytest.mark.parametrize('state,picked,blocks_next', [('reserved', 1, True), ('settled', 2, True),
                                                     ('settled', 3, False), ('failed', 0, False)])
def test_unique_active_guard_is_preserved(native, state, picked, blocks_next):
    db, session, _, _ = native
    insert_round(db, session, 'prior', 'guard:actor', state=state, picked=picked)
    if blocks_next:
        with pytest.raises(sqlite3.IntegrityError):
            insert_round(db, session, 'next', 'guard:actor', state='intent', picked=0)
    else:
        insert_round(db, session, 'next', 'guard:actor', state='intent', picked=0)


def test_existing_database_adds_history_index_without_changing_data_or_identity(native):
    db, session, _, path = native
    insert_round(db, session, 'saved-outcome', 'history-test:returning', win=True)
    db.execute('DROP INDEX agency_actor_history')
    before = list(db.iterdump())
    identity = db.execute('SELECT * FROM native_deployment_identity').fetchall()
    guards = db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name").fetchall()
    agency._initialized.discard(str(path.resolve()))
    agency.validate_config()
    after = [line for line in db.iterdump() if not line.startswith('CREATE INDEX agency_actor_history')]
    assert after == before
    assert db.execute('SELECT * FROM native_deployment_identity').fetchall() == identity
    assert db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name").fetchall() == guards
    assert db.execute('PRAGMA synchronous').fetchone()[0] == 2
    assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    assert db.execute("SELECT count(*) FROM sqlite_master WHERE name='agency_actor_history'").fetchone()[0] == 1
    agency._initialized.discard(str(path.resolve()))
    agency.validate_config()
    assert [line for line in db.iterdump() if not line.startswith('CREATE INDEX agency_actor_history')] == before
