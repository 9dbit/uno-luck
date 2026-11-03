"""CP16 source authority, ledger capture and command idempotency. Local SQLite only."""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import sqlite3
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from app import spin, orbit, round_outbox, wallet_link as wallet
from app.main import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('CI','true');monkeypatch.setenv('GAMEOPS_TEST_MODE','1')
    monkeypatch.setenv('GAMEOPS_ROUNDS_ENABLED','1');monkeypatch.setenv('GAMEOPS_ENVIRONMENT','staging')
    monkeypatch.setenv('GAMEOPS_BRIDGE_KEY_ID','ci-wallet-rounds');monkeypatch.setenv('GAMEOPS_BRIDGE_SECRET','ab'*32)
    monkeypatch.setenv('GAMEOPS_BRIDGE_ENABLED','0')
    monkeypatch.setenv('GAMEOPS_WALLET_ENABLED','1');monkeypatch.setenv('GAMEOPS_WALLET_COMMANDS_ENABLED','1')
    monkeypatch.setenv('GAMEOPS_WALLET_KEY_ID','ci-source-wallet');monkeypatch.setenv('GAMEOPS_WALLET_SECRET','cd'*32)
    monkeypatch.setenv('UNO_SPIN_DB_PATH',str(tmp_path/'game.sqlite3'))
    monkeypatch.setattr(round_outbox,'start',lambda:lambda:None)
    monkeypatch.setattr(wallet,'start',lambda:lambda:None)
    spin.INITIALIZED.clear();orbit._initialized.clear();round_outbox._READY.clear();wallet._READY.clear()
    with TestClient(app,raise_server_exceptions=False) as c:
        r=c.get('/api/orbit/state');assert r.status_code==200,r.text
        yield c

def account():
    db=spin.connection();a=dict(db.execute('SELECT * FROM accounts').fetchone());db.close();return a

def snapshot():
    db=spin.connection();a=account();p=wallet.snapshot(db,a['id']);db.close();return p

def cmd(action='credit',amount='25',expected=None):
    p=snapshot()
    c={'id':str(uuid.uuid4()),'game':'uno-luck','environment':'staging','stream_id':p['stream_id'],
       'player_ref':p['player_ref'],'action':action,'amount':amount,'expected_version':expected or p['snapshot']['version'],
       'expires_at':wallet.utc(time.time()+600)}
    c['request_hash']=wallet.command_hash(c)
    return c

def apply(c):
    db=spin.connection()
    try:return wallet.apply_command(db,account()['id'],c)
    finally:db.close()

def test_welcome_and_bonus_ledger_are_source_truth(client):
    p=snapshot();assert p['snapshot']['balance']=='1000' and p['snapshot']['version']=='1'
    assert p['entries'][0]['reason']=='welcome'
    response=client.post('/api/spin/daily',headers={'x-uno-client':'spin-ui'})
    assert response.status_code==200
    p=snapshot();assert p['snapshot']['balance']=='1250' and p['snapshot']['version']=='2'
    assert p['entries'][1]['reason']=='daily'
    previous=wallet.ZERO
    for e in p['entries']:
        assert wallet.entry_hash(previous,e['version'],e['entry_id'],e['reason'],e['delta'],e['balance_before'],e['balance_after'],e['occurred_at'])==e['chain_hash']
        previous=e['chain_hash']
    assert p['snapshot']['manifest']==previous
    assert account()['id'] not in json.dumps(p)
    assert account()['token_hash'] not in json.dumps(p)
    assert client.cookies.get(spin.COOKIE) not in json.dumps(p)

def test_adjustment_applies_once_with_source_version_and_persisted_receipt(client):
    c=cmd();r=apply(c);assert r['status']=='applied' and r['balance']==1025 and r['version']==2
    assert apply(c)['status']=='applied' and account()['balance']==1025
    wallet._READY.clear();spin.INITIALIZED.clear()
    assert apply(c)['entry_id']=='admin.'+c['id']
    p=snapshot();assert len(p['entries'])==2
    assert p['receipts'][0]['command_id']==c['id']
    assert p['receipts'][0]['status']=='applied'
    forged={**c,'amount':'900'};forged['request_hash']=wallet.command_hash(forged)
    with pytest.raises(RuntimeError,match='ID conflict'):apply(forged)
    assert account()['balance']==1025

def test_debit_never_overdraws_and_two_commands_cannot_share_expected_version(client):
    a=cmd('debit','600');b=cmd('debit','600')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(apply,[a,b]))
    assert sum(x['status']=='applied' for x in result)==1
    assert account()['balance']==400
    assert next(x for x in result if x['status']=='failed')['code']=='source_version_conflict'
    failed=apply(cmd('debit','500'));assert failed['code']=='insufficient_balance'
    assert account()['balance']==400

def test_expired_and_disabled_commands_fail_without_change(client,monkeypatch):
    c=cmd();c['expires_at']=wallet.utc(time.time()-10);c['request_hash']=wallet.command_hash(c)
    assert apply(c)['code']=='command_expired'
    monkeypatch.setenv('GAMEOPS_WALLET_COMMANDS_ENABLED','0')
    assert apply(cmd())['code']=='source_commands_disabled'
    assert account()['balance']==1000

def test_active_round_cannot_be_administratively_adjusted(client):
    r=client.post('/api/orbit/pick',headers={'x-uno-client':'spin-ui'},json={'request_id':uuid.uuid4().hex,'stake':25})
    assert r.status_code==200
    assert snapshot()['snapshot']['active_round'] is True
    assert apply(cmd())['code']=='active_round'
    assert account()['balance']==975
    for _ in range(2):
        r=client.post('/api/orbit/pick',headers={'x-uno-client':'spin-ui'},json={'request_id':uuid.uuid4().hex,'stake':25});assert r.status_code==200
    assert snapshot()['snapshot']['active_round'] is False
    assert apply(cmd())['status']=='applied'

def test_sql_trigger_failure_rolls_back_balance_and_command_receipt(client):
    c=cmd()
    db=spin.connection();db.execute("CREATE TRIGGER synthetic_block_journal BEFORE INSERT ON gameops_wallet_journal BEGIN SELECT RAISE(ABORT,'synthetic_failure'); END");db.close()
    with pytest.raises(sqlite3.IntegrityError):apply(c)
    assert account()['balance']==1000
    db=spin.connection();assert db.execute('SELECT count(*) FROM gameops_wallet_commands').fetchone()[0]==0
    db.execute('DROP TRIGGER synthetic_block_journal');db.close()
    assert apply(c)['status']=='applied'

def test_player_request_requires_session_is_idempotent_and_does_not_credit(client):
    payload={'request_id':str(uuid.uuid4()),'amount':40,'note':'QA player virtual credit request'}
    r=client.post('/api/gameops/wallet-request',headers={'x-uno-client':'spin-ui'},json=payload)
    assert r.status_code==200,r.text
    assert r.json()['balance_changed'] is False
    again=client.post('/api/gameops/wallet-request',headers={'x-uno-client':'spin-ui'},json=payload)
    assert again.json()['replay'] is True
    conflict=client.post('/api/gameops/wallet-request',headers={'x-uno-client':'spin-ui'},json={**payload,'amount':45})
    assert conflict.status_code==409
    assert len(snapshot()['requests'])==1
    assert account()['balance']==1000
    client.cookies.clear()
    assert client.get('/api/gameops/wallet-status').status_code==401
    assert client.post('/api/gameops/wallet-request',headers={'x-uno-client':'spin-ui'},json={**payload,'request_id':str(uuid.uuid4())}).status_code==401

def test_invalid_scopes_and_hashes_cannot_apply(client):
    c=cmd()
    for field,value in [('stream_id',str(uuid.uuid4())),('environment','production'),('player_ref','p_'+'e'*64),('request_hash','0'*64)]:
        other={**c,field:value}
        with pytest.raises(RuntimeError):apply(other)
    assert account()['balance']==1000

def test_malformed_balance_evidence_is_never_exported(client):
    db=spin.connection();db.execute('UPDATE accounts SET balance=999');db.close()
    with pytest.raises(RuntimeError,match='cannot be proved'):snapshot()

def test_disabling_network_after_activation_preserves_source_journal(client,monkeypatch):
    assert snapshot()['snapshot']['balance']=='1000'
    monkeypatch.setenv('GAMEOPS_WALLET_ENABLED','0')
    wallet._READY.clear();spin.INITIALIZED.clear()
    r=client.post('/api/spin/daily',headers={'x-uno-client':'spin-ui'})
    assert r.status_code==200,r.text
    assert account()['balance']==1250
    db=spin.connection()
    row=db.execute('SELECT version,balance_after FROM gameops_wallet_journal ORDER BY id DESC LIMIT 1').fetchone()
    assert row['version']==2 and row['balance_after']==1250
    db.close()
    with TestClient(app,raise_server_exceptions=False) as fresh:
        response=fresh.get('/api/orbit/state')
        assert response.status_code==200,response.text
    monkeypatch.setenv('GAMEOPS_WALLET_ENABLED','1')
    wallet._READY.clear();spin.INITIALIZED.clear()
    assert snapshot()['snapshot']['balance']=='1250'
