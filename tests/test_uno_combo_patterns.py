"""UNO LUCK v1.2: real UNO-inspired card pattern determines rank, not the animation.

Odds and payout are intentionally unchanged. These are weighted virtual combos,
not the natural odds of shuffling a physical UNO deck.
"""
import collections

import pytest
from fastapi.testclient import TestClient

from app import orbit, spin
from app.main import app


def hand(color, *faces):
    return [{'color': color, 'face': face} for face in faces]


@pytest.mark.parametrize('rank,cards', [
    (1, hand('wild', '+4', '+4', '+4')),
    (2, hand('wild', 'WILD', 'WILD', 'WILD')),
    (3, hand('red', 'REVERSE', '+2', 'SKIP')),
    (4, hand('green', '5', '3', '4')),
    (5, hand('yellow', '8', '2', 'SKIP')),
])
def test_rank_is_visible_card_combination(rank, cards):
    assert orbit.classify_rank(cards) == rank
    assert orbit.CELEBRATIONS[rank]['pattern']
    assert orbit.CELEBRATIONS[rank]['rule']
    assert orbit.CELEBRATIONS[rank]['multiplier'] == (200,80,30,10,2)[rank-1]


@pytest.mark.parametrize('cards', [
    hand('wild', '+4', 'WILD', '+4'),
    hand('wild', 'WILD', 'WILD', '+4'),
    hand('red', '0', '0', '0'),  # no special rank; also impossible from one classic deck
    [{'color':'red','face':'SKIP'},
     {'color':'red','face':'REVERSE'},
     {'color':'blue','face':'+2'}],
    hand('blue','0','4','8'),
    [{'color':'red','face':'WILD'},
     {'color':'red','face':'WILD'},
     {'color':'red','face':'WILD'}],  # counterfeit: Wild must be uncolored
])
def test_no_false_premium_rank(cards):
    assert orbit.classify_rank(cards) not in (1,2,3,4)


@pytest.mark.parametrize('rank',range(1,6))
def test_generated_pattern_matches_classified_rank(monkeypatch,rank):
    monkeypatch.setattr(orbit,'choose_tier',lambda:rank)
    monkeypatch.setattr(orbit.secrets,'randbelow',lambda upper:0)
    for _ in range(25):
        cards=orbit.choose_cards()
        assert orbit.classify_rank(cards)==rank
        assert len(cards)==3
        if rank in (3,4,5):
            assert len({c['color'] for c in cards})==1
            counts=collections.Counter(c['face'] for c in cards)
            assert counts['0'] <= 1
            assert max(counts.values())<=2


def test_constant_probabilities_and_no_undocumented_bonus():
    assert orbit.RULES_VERSION==4
    assert orbit.WIN_PERCENT==80
    assert [orbit.CELEBRATIONS[i]['weight'] for i in range(1,6)]==[
        100,900,4000,30000,965000]
    assert [orbit.CELEBRATIONS[i]['multiplier'] for i in range(1,6)]==[
        200,80,30,10,2]
    rules=orbit.public_rules()
    assert rules['rules_version']==4
    assert sum(t['weight'] for t in orbit.CELEBRATIONS.values()) / 10000==100
    assert all('conditional_win_probability_percent' not in t for t in rules['celebrations'])


def test_live_api_keeps_pattern_secret_until_third_spin(tmp_path,monkeypatch):
    monkeypatch.setenv('UNO_SPIN_DB_PATH',str(tmp_path/'uno_pattern.sqlite'))
    spin.INITIALIZED.clear()
    orbit._initialized.clear()
    monkeypatch.setattr(orbit,'choose_cards',lambda:hand('blue','SKIP','REVERSE','+2'))
    def pick(client,i):
        return client.post('/api/orbit/pick',json={'request_id':f'pattern_card_round_phase_{i}'},
            headers={'X-UNO-Client':'spin-ui'})
    with TestClient(app) as client:
        assert client.get('/api/orbit/state').status_code==200
        for i in (1,2):
            result=pick(client,i).json()['round']
            assert result['tier'] is None and result['pattern'] is None
            assert result['payout'] is None
        result=pick(client,3).json()['round']
        assert result['tier']['rank']==3
        assert result['pattern']=='ACTION_TRIO'
        assert result['payout']==25*30
        assert [c['face'] for c in result['cards']]==['SKIP','REVERSE','+2']
        history=client.get('/api/orbit/state').json()['recent']
        assert history[0]['pattern']=='ACTION_TRIO'
        assert history[0]['tier']['rank']==3


def test_inflight_old_rank_is_honored_after_migration(tmp_path,monkeypatch):
    monkeypatch.setenv('UNO_SPIN_DB_PATH',str(tmp_path/'uno_legacy.sqlite'))
    spin.INITIALIZED.clear()
    orbit._initialized.clear()
    monkeypatch.setattr(orbit,'choose_cards',lambda:hand('blue','3','6','8'))
    def pick(client,i):
        return client.post('/api/orbit/pick',json={'request_id':f'legacy_compatibility_phase_{i}'},
            headers={'X-UNO-Client':'spin-ui'})
    with TestClient(app) as client:
        client.get('/api/orbit/state')
        assert pick(client,1).status_code==200
        db=spin.connection()
        try:
            db.execute('UPDATE orbit_rounds SET tier=1,rules_version=1 WHERE picked=1')
            db.commit()
        finally:
            db.close()
        assert pick(client,2).status_code==200
        done=pick(client,3).json()['round']
        assert done['tier']['rank']==1
        assert done['pattern']=='LEGACY_COLOR_MATCH'
        assert done['tier']['pattern']=='LEGACY_COLOR_MATCH'
        assert 'Ronde lama' in done['tier']['rule']
        assert done['payout']==25*200
