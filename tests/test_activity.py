"""Public payout activity does not fabricate social proof or disclose identities."""
import pytest
from fastapi.testclient import TestClient
from app import spin, orbit
from app.main import app


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('UNO_SPIN_DB_PATH',str(tmp_path/'activity.sqlite3'))
    monkeypatch.delenv('UNO_QA_ACTIVITY_DEMO',raising=False)
    spin.INITIALIZED.clear()
    orbit._initialized.clear()
    with TestClient(app) as c:
        c.get('/api/orbit/state')
        yield c


def test_live_activity_from_settled_spins_only_and_masks_names(client):
    from app.activity import alias
    db=orbit.open_db()
    account=db.execute('SELECT id FROM accounts LIMIT 1').fetchone()['id']
    db.execute('UPDATE accounts SET display_name=? WHERE id=?',
        ('Rahasia Nama Lengkap',account))
    db.execute("""INSERT INTO spins(id,account_id,request_id,stake,payout,
        delta,balance_after,combo,cards_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
        ('settled-1',account,'valid-settled-1',25,88000,87975,1000,
         'COLOR_MATCH','[]',100))
    db.execute("""INSERT INTO spins(id,account_id,request_id,stake,payout,
        delta,balance_after,combo,cards_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
        ('settled-2',account,'valid-settled-2',50,0,-50,950,
         'NO_MATCH','[]',101))
    db.close()
    result=client.get('/api/activity/public')
    assert result.status_code==200
    assert result.headers['cache-control']=='no-store'
    data=result.json()
    assert data['mode']=='live' and data['total_bet_coin']==75
    assert data['recent']==[{'name':alias(account),'payout_coin':88000}]
    assert data['recent'][0]['name'].endswith('**')
    assert 'Rahasia' not in result.text
    assert '889980250' not in result.text
    assert 'Coin virtual' in result.text


def test_qa_simulation_is_always_explicitly_labeled(client,monkeypatch):
    monkeypatch.setenv('UNO_QA_ACTIVITY_DEMO','1')
    result=client.get('/api/activity/public')
    assert result.status_code==200
    data=result.json()
    assert data['mode']=='simulation'
    assert 'SIMULASI' in data['label']
    assert data['demo_start_coin']==889980250
    assert data['recent']==[
        {'name':'maxw**','payout_coin':88000},
        {'name':'sutris**','payout_coin':242250},
        {'name':'zom**','payout_coin':74000}]
    assert all(item['name'].endswith('**') for item in data['recent'])
    assert 'total_bet_coin' not in data
