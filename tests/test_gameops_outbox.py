"""CP15: true server settlement + SQLite outbox, no production contact."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import uuid
import pytest
from fastapi.testclient import TestClient
from app import orbit, spin, round_outbox as outbox
from app.main import app

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('CI','true')
    monkeypatch.setenv('GAMEOPS_TEST_MODE','1')
    monkeypatch.setenv('GAMEOPS_ROUNDS_ENABLED','1')
    monkeypatch.setenv('GAMEOPS_ENVIRONMENT','staging')
    monkeypatch.setenv('GAMEOPS_BRIDGE_KEY_ID','ci-outbox-test')
    monkeypatch.setenv('GAMEOPS_BRIDGE_SECRET','ab'*32)
    monkeypatch.setenv('GAMEOPS_BRIDGE_ENABLED','0')
    monkeypatch.setenv('UNO_SPIN_DB_PATH',str(tmp_path/'game.sqlite3'))
    monkeypatch.setattr(outbox,'start',lambda:lambda:None) # Don't create a network worker in unit tests.
    spin.INITIALIZED.clear();orbit._initialized.clear();outbox._READY.clear()
    with TestClient(app,raise_server_exceptions=False) as c:
        assert c.get('/api/orbit/state').status_code==200
        yield c

def pick(c,key=None):
    return c.post('/api/orbit/pick',headers={'x-uno-client':'spin-ui'},json={'request_id':key or uuid.uuid4().hex,'stake':25})

def rows():
    db=spin.connection()
    try:return [dict(x) for x in db.execute('SELECT * FROM gameops_round_outbox')]
    finally:db.close()

def test_finished_round_is_atomically_observed_and_replays_do_not_duplicate(client):
    assert pick(client).json()['round']['picked']==1
    assert pick(client).json()['round']['picked']==2
    assert rows()==[]
    key=uuid.uuid4().hex
    final=pick(client,key);assert final.status_code==200
    r=final.json()['round'];stored=rows();assert len(stored)==1
    event=json.loads(stored[0]['payload'])
    assert event['stake']==str(r['stake'])
    assert event['payout']==str(r['payout'])
    assert event['round_id']==r['id']
    assert event['source_sequence']=='1'
    assert event['environment']=='staging'
    assert event['player_ref'].startswith('p_') and len(event['player_ref'])==66
    assert pick(client,key).json()['replayed'] is True
    assert len(rows())==1
    db=spin.connection();acct=db.execute('SELECT * FROM accounts').fetchone();db.close()
    assert acct['id'] not in stored[0]['payload'] and acct['token_hash'] not in stored[0]['payload']
    assert client.cookies.get(spin.COOKIE) not in stored[0]['payload']

def test_capture_failure_rolls_back_round_and_payout(client,monkeypatch):
    pick(client);pick(client)
    original=outbox.capture
    monkeypatch.setattr(outbox,'capture',lambda *args:(_ for _ in ()).throw(RuntimeError('synthetic failure')))
    key=uuid.uuid4().hex
    assert pick(client,key).status_code==500
    assert rows()==[]
    db=spin.connection();assert db.execute('SELECT count(*) FROM spins').fetchone()[0]==0
    assert db.execute('SELECT picked FROM orbit_rounds').fetchone()[0]==2
    balance=db.execute('SELECT balance FROM accounts').fetchone()[0];db.close()
    assert balance==975
    monkeypatch.setattr(outbox,'capture',original)
    assert pick(client,key).status_code==200
    assert rows()[0]['sequence']==1

def test_snapshot_reads_source_records_not_just_queue(client):
    pick(client);pick(client);pick(client)
    db=spin.connection();snap=outbox.source_snapshot(db)
    event=json.loads(rows()[0]['payload'])
    assert snap['expected_count']=='1'
    assert snap['manifest_hash']==hashlib.sha256(outbox.manifest_line(event)).hexdigest()
    db.execute('DELETE FROM gameops_round_outbox')
    with pytest.raises(RuntimeError,match='gap'):
        outbox.source_snapshot(db)
    db.close()

def test_effective_capped_legacy_payout_matches_balance_change(client,monkeypatch):
    db=spin.connection();db.execute('UPDATE accounts SET balance=?',(spin.COIN_CAP-3,));db.close()
    monkeypatch.setattr(spin,'fresh_cards',lambda:[{'color':'red','face':'7'}]*3)
    result=client.post('/api/spin/place',headers={'x-uno-client':'spin-ui'},json={'request_id':uuid.uuid4().hex,'stake':10})
    assert result.status_code==200
    assert result.json()['payout']==20 # Existing theoretical payout contract unchanged.
    assert result.json()['balance']==spin.COIN_CAP
    event=json.loads(rows()[0]['payload'])
    assert event['payout']=='13' and event['stake']=='10' # effective credited net 3, not an invented 10.

def test_retry_keeps_payload_and_does_not_ack_unsigned_delivery(client,monkeypatch):
    pick(client);pick(client);pick(client)
    before=rows()[0]['payload']
    monkeypatch.setattr(outbox,'exchange',lambda *args:(_ for _ in ()).throw(RuntimeError('receipt_signature_invalid')))
    outbox.tick();x=rows()[0]
    assert x['acknowledged_at'] is None and x['attempts']==1 and x['payload']==before
    db=spin.connection();db.execute('UPDATE gameops_round_outbox SET next_attempt=0');db.close()
    def receipt(e):
        if e['type']=='round.settled':return {'id':'99','type':e['type'],'accepted':True}
        return {'type':e['type'],'status':'matched','received_count':'1','through_sequence':'1'}
    monkeypatch.setattr(outbox,'exchange',receipt)
    outbox.tick();assert rows()[0]['acknowledged_at'] is not None
    assert rows()[0]['payload']==before and rows()[0]['receipt_id']=='99'

def test_queue_survives_reopen_and_gap_detection_is_durable(client):
    pick(client);pick(client);pick(client)
    original=rows()[0]['payload'];outbox._READY.clear();spin.INITIALIZED.clear()
    db=spin.connection();assert outbox.source_snapshot(db)['expected_count']=='1';db.close()
    assert rows()[0]['payload']==original

def test_enabled_export_refuses_production_scope(client,monkeypatch):
    monkeypatch.setenv('GAMEOPS_ENVIRONMENT','production')
    with pytest.raises(RuntimeError,match='staging'):
        outbox.config()
