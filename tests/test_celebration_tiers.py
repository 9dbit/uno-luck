"""v1.0 server-authoritative 5-tier virtual coin settlement contracts."""
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from app import orbit, spin
from app.main import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('UNO_SPIN_DB_PATH',str(tmp_path/'celebrate.sqlite3'))
    spin.INITIALIZED.clear();orbit._initialized.clear()
    with TestClient(app) as c:
        assert c.get('/api/orbit/state').status_code==200
        yield c

def pick(c,id,stake=25):
    return c.post('/api/orbit/pick',headers={'x-uno-client':'spin-ui'},json={'request_id':id,'stake':stake})

def matched():return [{'color':'blue','face':f} for f in ['3','6','8']]

def mismatch():return [{'color':c,'face':'7'} for c in ('blue','red','yellow')]

def test_probability_thresholds_and_server_independence(monkeypatch):
    assert sum(t['weight'] for t in orbit.CELEBRATIONS.values())==1_000_000
    bounds=[(0,1),(99,1),(100,2),(999,2),(1000,3),(4999,3),(5000,4),(34999,4),(35000,5),(999999,5)]
    for result,expected in bounds:
        monkeypatch.setattr(orbit.secrets,'randbelow',lambda n,result=result:result)
        assert orbit.choose_tier()==expected
    rules=orbit.public_rules()
    assert sum(v['weight'] for v in orbit.CELEBRATIONS.values()) / 10000==100
    assert orbit.WIN_PERCENT==80
    assert [t['multiplier'] for t in rules['celebrations']]==[200,80,30,10,2]

@pytest.mark.parametrize('rank,multiplier',[(1,200),(2,80),(3,30),(4,10),(5,2)])
def test_each_rank_exactly_settled_once(client,monkeypatch,rank,multiplier):
    monkeypatch.setattr(orbit,'choose_cards',lambda:orbit.cards_for_tier(rank))
    prefix=f'celebrate_rank_{rank}'
    first=pick(client,prefix+'_phase_one').json()
    assert first['round']['tier'] is None and first['account']['balance']==975
    duplicate=pick(client,prefix+'_phase_one').json()
    assert duplicate['replayed'] is True and duplicate['round']['tier'] is None
    assert pick(client,prefix+'_phase_two').json()['round']['tier'] is None
    end=pick(client,prefix+'_phase_three').json()
    assert end['round']['combo']=='COLOR_MATCH'
    assert end['round']['tier']['rank']==rank
    assert end['round']['tier']['multiplier']==multiplier
    assert end['round']['payout']==multiplier*25
    assert end['round']['delta']==(multiplier-1)*25
    assert end['account']['balance']==1000+(multiplier-1)*25
    assert pick(client,prefix+'_phase_three').json()['replayed'] is True
    assert client.get('/api/orbit/state').json()['recent'][0]['tier']['rank']==rank
    db=spin.connection()
    try:
        payout_entries=db.execute("SELECT COUNT(*) AS n FROM ledger WHERE reason='orbit_payout'").fetchone()['n']
        assert payout_entries==1
        round_tier=db.execute('SELECT tier FROM orbit_rounds').fetchone()['tier']
        assert round_tier==rank
    finally:db.close()

def test_no_match_never_has_tier_or_payout(client,monkeypatch):
    monkeypatch.setattr(orbit,'choose_cards',mismatch)
    monkeypatch.setattr(orbit,'choose_tier',lambda:(_ for _ in ()).throw(AssertionError('must not roll tier on loss')))
    for i in (1,2):pick(client,f'no_match_phase_{i}')
    last=pick(client,'no_match_phase_3').json()
    assert last['round']['tier'] is None
    assert last['round']['combo']=='NO_MATCH'
    assert last['round']['payout']==0

def test_max_wallet_cap_is_actual_credited_not_fake_advertised_payout(client,monkeypatch):
    monkeypatch.setattr(orbit,'choose_cards',lambda:orbit.cards_for_tier(1))
    db=spin.connection();db.execute('UPDATE accounts SET balance=999990');db.close()
    for i in range(1,4):response=pick(client,f'coin_cap_phase_{i}',250)
    round_=response.json()['round'];acct=response.json()['account']
    assert round_['tier']['multiplier']==200
    assert acct['balance']==spin.COIN_CAP
    assert round_['payout']==260
    assert round_['delta']==10
    # The actual amount credited is less than the nominal 50,000 coins due to the disclosed wallet cap.

def test_existing_v09_table_migrates_without_losing_guest(client):
    db=spin.connection()
    db.execute('DROP TABLE orbit_rounds')
    db.execute('''CREATE TABLE orbit_rounds(id TEXT PRIMARY KEY,account_id TEXT NOT NULL,
      start_key TEXT NOT NULL,stake INTEGER NOT NULL,cards_json TEXT NOT NULL,
      picked INTEGER NOT NULL,payout INTEGER NOT NULL DEFAULT 0,
      combo TEXT NOT NULL,created_at REAL NOT NULL,finished_at REAL)''')
    db.commit()
    orbit._initialized.clear()
    orbit.create_schema(db)
    columns = {r['name'] for r in db.execute('PRAGMA table_info(orbit_rounds)')}
    assert 'tier' in columns and 'rules_version' in columns
    db.close()
    assert client.get('/api/orbit/state').status_code==200

def test_frontend_images_sounds_and_celebration_are_real_assets():
    root=Path(__file__).resolve().parents[1]
    html=(root/'app/static/orbit-index.html').read_text()
    js=(root/'app/static/orbit.js').read_text()
    assert '<h1 class="motion-title">DRAGON SPIN</h1>' in html
    assert 'celebration-overlay' in html
    assert "await window.UNOLuckCelebration?.present(last)" in js
    assert 'celebrations.js' in html and 'sound.js' in html
    for i in range(1,6):
        assert (root/f'app/static/art/v3/tier-{i}.webp').stat().st_size>20000
        audio=(root/f'app/static/audio/tier-{i}.mp3').read_bytes()
        assert len(audio)>10000
        assert audio[:3]==b'ID3' or audio[:2]==b'\xff\xfb'
    assert (root/'app/static/audio/music-loop.mp3').stat().st_size>30000
    css=(root/'app/static/art/celebrations.css').read_text()
    assert 'wheel-led-ring' in css and 'full-bright' in css
    assert 'clamp(78px,24%,126px)' in css
