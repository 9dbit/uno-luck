"""Three-click UNO LUCK circular card spin. Koin are virtual and non-redeemable.

The three selected cards are chosen server-side at round creation and revealed
one by one. Exactly 80% of the outcome generator's base gate qualifies for one
of five UNO-inspired card patterns (20% NO_MATCH). Rank is derived from the
actual three-card hand, never drawn independently after the cards exist.
One round costs one stake; all coins remain non-redeemable virtual credits.
"""
from __future__ import annotations

import json
import re
import secrets
import time
import sqlite3
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import spin, economy, autoplay

router = APIRouter(prefix="/api/orbit", tags=["UNO LUCK Orbit"])
WIN_PERCENT = 80
RULES_VERSION = 4
FACES = spin.FACES
COLORS = spin.COLORS
ACTION_TRIO = frozenset(('SKIP', 'REVERSE', '+2'))

# Unchanged per-winning-round weights (millionths) and payout table.
# Each weight now controls which card-pattern template gets generated.
# The authoritative payout rank is independently CLASSIFIED FROM THE CARDS.
CELEBRATIONS = {
    1: {'title': 'DRAGON KING JACKPOT', 'theme': 'dragon', 'multiplier': 200,
        'weight': 100, 'pattern': 'TRIPLE_DRAW_FOUR',
        'rule': '3 kartu Wild Draw Four (+4)'},
    2: {'title': 'IMPERIAL FORTUNE', 'theme': 'imperial', 'multiplier': 80,
        'weight': 900, 'pattern': 'TRIPLE_WILD',
        'rule': '3 kartu Wild (ganti warna)'},
    3: {'title': 'PHOENIX COLOR BLAST', 'theme': 'phoenix', 'multiplier': 30,
        'weight': 4000, 'pattern': 'ACTION_TRIO',
        'rule': 'Skip + Reverse + Draw Two (+2), semuanya satu warna'},
    4: {'title': 'GOLDEN MATCH', 'theme': 'emerald', 'multiplier': 10,
        'weight': 30000, 'pattern': 'COLOR_STRAIGHT',
        'rule': '3 angka berurutan (0-9), semuanya satu warna'},
    5: {'title': 'LUCKY COLOR WIN', 'theme': 'ruby', 'multiplier': 2,
        'weight': 965000, 'pattern': 'COLOR_MATCH',
        'rule': '3 kartu satu warna, selain kombinasi Rank 3 dan 4'},
}
WEIGHT_SCALE = 1_000_000
assert sum(t['weight'] for t in CELEBRATIONS.values()) == WEIGHT_SCALE


def choose_tier() -> int:
    """Draw a winning HAND TEMPLATE with unchanged cryptographic weights.

    The payout rank is still classified from real card faces, not this draw.
    No daily quota, pity timer, user-linked adjustment, or client RNG.
    """
    roll = secrets.randbelow(WEIGHT_SCALE)
    for rank in sorted(CELEBRATIONS):
        roll -= CELEBRATIONS[rank]['weight']
        if roll < 0:
            return rank
    raise RuntimeError('tier probability table invalid')


def rank_details(rank: int | None, *, legacy: bool = False) -> dict | None:
    if rank not in CELEBRATIONS:
        return None
    tier = CELEBRATIONS[rank]
    details = {k: tier[k] for k in ('title', 'theme', 'multiplier', 'pattern', 'rule')} | {'rank': rank}
    if legacy:
        details['pattern'] = 'LEGACY_COLOR_MATCH'
        details['rule'] = 'Ronde lama: tiga kartu satu warna, dengan Rank versi sebelum perubahan kombinasi'
    return details


class PickRequest(BaseModel):
    request_id: str = Field(min_length=12, max_length=80)
    stake: int = 25
    auto_session_id: str | None = None


def create_schema(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS orbit_rounds (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL REFERENCES accounts(id),
            start_key TEXT NOT NULL,
            stake INTEGER NOT NULL,
            charged_stake INTEGER,
            auto_session_id TEXT,
            promo_coin INTEGER NOT NULL DEFAULT 0,
            cards_json TEXT NOT NULL,
            picked INTEGER NOT NULL CHECK(picked BETWEEN 1 AND 3),
            payout INTEGER NOT NULL DEFAULT 0,
            combo TEXT NOT NULL,
            tier INTEGER CHECK(tier BETWEEN 1 AND 5),
            rules_version INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL,
            finished_at REAL,
            UNIQUE(account_id,start_key)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ix_orbit_account_active
            ON orbit_rounds(account_id) WHERE picked < 3;
        CREATE TABLE IF NOT EXISTS orbit_requests (
            account_id TEXT NOT NULL REFERENCES accounts(id),
            request_id TEXT NOT NULL,
            round_id TEXT NOT NULL REFERENCES orbit_rounds(id),
            selected_count INTEGER NOT NULL,
            PRIMARY KEY(account_id,request_id)
        );
    """)
    # Existing guest rounds survive the upgrade; legacy matching rounds default
    # to the previous 2x when they are eventually completed.
    economy.schema(db)
    autoplay.schema(db)
    existing = {r['name'] for r in db.execute('PRAGMA table_info(orbit_rounds)').fetchall()}
    if 'tier' not in existing:
        db.execute('ALTER TABLE orbit_rounds ADD COLUMN tier INTEGER CHECK(tier BETWEEN 1 AND 5)')
    # Old/unfinished rounds keep their original pre-pattern rank and payout.
    if 'rules_version' not in existing:
        db.execute('ALTER TABLE orbit_rounds ADD COLUMN rules_version INTEGER NOT NULL DEFAULT 1')

    if 'economy_json' not in existing:
        db.execute('ALTER TABLE orbit_rounds ADD COLUMN economy_json TEXT')
    if 'charged_stake' not in existing:
        db.execute('ALTER TABLE orbit_rounds ADD COLUMN charged_stake INTEGER')
    if 'auto_session_id' not in existing:
        db.execute('ALTER TABLE orbit_rounds ADD COLUMN auto_session_id TEXT')
    if 'promo_coin' not in existing:
        db.execute('ALTER TABLE orbit_rounds ADD COLUMN promo_coin INTEGER NOT NULL DEFAULT 0')
    db.execute('UPDATE orbit_rounds SET charged_stake=stake WHERE charged_stake IS NULL')


def open_db() -> sqlite3.Connection:
    db = spin.connection()
    with spin.SCHEMA_LOCK:
        if spin.database_path() not in _initialized:
            create_schema(db)
            _initialized.add(spin.database_path())
    return db


_initialized: set[str] = set()


def classify_rank(cards: list[dict]) -> int | None:
    """Classify EXACTLY the displayed three UNO-inspired cards.

    Ordered from most specific pattern to broad Color Match. Wild cards have
    NO color; only triple Wild or triple +4 are winning wild combinations.
    This is UNO LUCK's custom reward system, not a rule of Mattel UNO.
    """
    if len(cards) != 3 or not all(isinstance(card, dict) for card in cards):
        return None
    colors = [card.get('color') for card in cards]
    faces = [str(card.get('face')) for card in cards]
    if colors == ['wild'] * 3:
        if faces == ['+4'] * 3:
            return 1
        if faces == ['WILD'] * 3:
            return 2
        return None  # mixed Wild/+4 is not a paid pattern
    if len(set(colors)) != 1 or colors[0] not in COLORS:
        return None
    if frozenset(faces) == ACTION_TRIO and len(set(faces)) == 3:
        return 3
    if all(face in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9') for face in faces):
        numbers = sorted(int(face) for face in faces)
        if numbers[1] == numbers[0] + 1 and numbers[2] == numbers[1] + 1:
            return 4
    if all(face in FACES for face in faces):
        return 5
    return None


def cards_for_tier(rank: int) -> list[dict]:
    """Generate a recognizable 3-card pattern using a CSPRNG.

    Patterns are consistent with quantities in one classic 108-card UNO deck:
    four Wild +4, four Wild, each colored 0 once and 1-9/action twice.
    Each round is a weighted virtual outcome, NOT an unweighted deck shuffle.
    """
    if rank == 1:
        return [{'color': 'wild', 'face': '+4'} for _ in range(3)]
    if rank == 2:
        return [{'color': 'wild', 'face': 'WILD'} for _ in range(3)]
    if rank not in (3, 4, 5):
        raise ValueError('Unknown combination rank')
    color = secrets.choice(COLORS)
    if rank == 3:
        faces = ['SKIP', 'REVERSE', '+2']
    elif rank == 4:
        start = secrets.randbelow(8)  # 0-1-2 through 7-8-9
        faces = [str(start + offset) for offset in range(3)]
    else:
        for _ in range(100):
            faces = [secrets.choice(FACES) for _ in range(3)]
            if faces.count('0') > 1 or len(set(faces)) == 1:
                continue  # avoid combinations impossible in a single deck
            sample = [{'color': color, 'face': face} for face in faces]
            if classify_rank(sample) == 5:
                break
        else:
            raise RuntimeError('Could not generate ordinary Color Match')
    secrets.SystemRandom().shuffle(faces)
    return [{'color': color, 'face': face} for face in faces]


def choose_cards() -> list[dict]:
    """80% winning pattern vs 20% non-winning, unchanged odds."""
    winner = secrets.randbelow(100) < WIN_PERCENT
    if winner:
        sampled_template = choose_tier()
        cards = cards_for_tier(sampled_template)
        # Server must pay what the actual cards represent, never a separate roll.
        if classify_rank(cards) != sampled_template:
            raise RuntimeError('Card combination and payout rank disagree')
        return cards
    colors = [secrets.choice(COLORS) for _ in range(3)]
    if len(set(colors)) == 1:
        colors[2] = secrets.choice([c for c in COLORS if c != colors[0]])
    cards = [{'color': color, 'face': secrets.choice(FACES)} for color in colors]
    if classify_rank(cards) is not None:
        raise RuntimeError('NO_MATCH accidentally generated a winning pattern')
    return cards


def current_round(db: sqlite3.Connection, aid: str):
    return db.execute("SELECT * FROM orbit_rounds WHERE account_id=? AND picked<3 LIMIT 1", (aid,)).fetchone()


def view_round(round_row, phase: int | None = None) -> dict | None:
    if round_row is None:
        return None
    picked = round_row['picked'] if phase is None else min(phase, round_row['picked'])
    dealt = json.loads(round_row['cards_json'])
    cards = dealt[:picked]
    complete = picked == 3
    saved_rank = (round_row['tier'] or 5) if round_row['combo'] == 'COLOR_MATCH' else None
    version = int(round_row['rules_version'])
    if complete and version >= 3 and round_row['combo'] == 'COLOR_MATCH':
        if classify_rank(dealt) != saved_rank:
            raise RuntimeError('Stored prize rank contradicts actual dealt cards')
    pattern = None
    if complete and round_row['combo'] == 'COLOR_MATCH':
        pattern = (CELEBRATIONS[saved_rank]['pattern']
                   if version >= 3 and saved_rank in CELEBRATIONS
                   else 'LEGACY_COLOR_MATCH')
    tier_view = rank_details(saved_rank, legacy=version < RULES_VERSION) if complete and saved_rank else None
    snap = json.loads(round_row['economy_json']) if round_row['economy_json'] else None
    if tier_view and snap:
        tier_view['multiplier'] = snap['multiplier']
    return {
        'id': round_row['id'], 'picked': picked, 'stake': round_row['stake'],
        'charged_stake': round_row['charged_stake'], 'free_spin': bool(round_row['auto_session_id'] and round_row['charged_stake'] == 0),
        'cards': cards, 'complete': complete,
        'combo': round_row['combo'] if complete else None,
        'tier': tier_view,
        'bonus': {'kind':round_row['combo'],'multiplier':snap['multiplier']} if complete and snap and round_row['combo'] in ('PAIR_SUM','PAIR_PRODUCT','COLOR_PAIR','COLOR_SEQUENCE') else None,
        'pattern': pattern, 'rules_version': version,
        'payout': round_row['payout'] if complete else None,
        'promo_coin': round_row['promo_coin'] if complete else None,
        'delta': (round_row['payout'] + round_row['promo_coin'] - round_row['charged_stake']) if complete else None,
    }


def public_rules(config=None) -> dict:
    tiers = [rank_details(rank) for rank in sorted(CELEBRATIONS)]
    if config:
        for tier in tiers:
            tier['multiplier'] = config.multipliers[tier['rank']-1]
        tiers[-1]['rule'] += ', selain bonus pasangan angka / Draw Two'
    return {
        'mode': 'three-pick-orbit', 'virtual_only': True, 'rules_version': RULES_VERSION,
        'stake_options': config.stake_options if config else spin.COSTS,
        'virtual_rp_per_coin': economy.VIRTUAL_RP_PER_COIN,
        'numeric_bonus': {'sum_cap':config.sum_cap,'product_cap':config.product_cap,
                          'draw_two_match':True} if config else None,
        'base_payout_multiplier': config.multipliers[4] if config else 2, 'payout_multiplier': config.multipliers[4] if config else 2,
        'celebrations': tiers,
        'coin_cap': spin.COIN_CAP,
        'spin_sequence': ['kiri','tengah','kanan'],
        'note': 'Setiap ronde 3 SPIN dan 1 biaya. Payout rank ditentukan dari 3 kartu yang benar-benar muncul. NO MATCH tidak mendapat payout. Saldo dapat dibatasi 1.000.000 koin. Tidak ada uang, deposit, atau pencairan. Bukan permainan resmi UNO.',
    }


@router.get('/state')
def state(request: Request, response: Response):
    db = open_db()
    try:
        account = spin.get_account(request,response,db)
        row = current_round(db, account['id'])
        hist = spin.spin_history(db, account['id'], 8)
        for item in hist:
            tier_row = db.execute('SELECT tier,rules_version,cards_json,economy_json FROM orbit_rounds WHERE id=? AND account_id=?', (item['id'], account['id'])).fetchone()
            version = int(tier_row['rules_version']) if tier_row else 1
            item['tier'] = (rank_details(tier_row['tier'] or 5, legacy=version < RULES_VERSION)
                if tier_row and item['combo'] == 'COLOR_MATCH' else None)
            item['pattern'] = (CELEBRATIONS[tier_row['tier']]['pattern']
                if tier_row and version >= 3 and item['combo'] == 'COLOR_MATCH'
                and tier_row['tier'] in CELEBRATIONS else
                'LEGACY_COLOR_MATCH' if tier_row and item['combo'] == 'COLOR_MATCH' else None)
            if tier_row and tier_row['economy_json'] and item['tier']:
                item['tier']['multiplier'] = json.loads(tier_row['economy_json'])['multiplier']
            item['rules_version'] = version
        response.headers['Cache-Control'] = 'no-store'
        return {'account': spin.account_view(account), 'round': view_round(row),
                'recent': hist, 'rules': public_rules(economy.active(db)[1])}
    finally:
        db.close()


def validate_input(payload: PickRequest) -> None:
    if not re.fullmatch('[A-Za-z0-9_-]{12,80}',payload.request_id):
        raise HTTPException(422,'request_id tidak valid')
    if type(payload.stake) is not int or payload.stake <= 0:
        raise HTTPException(422,'Biaya SPIN tidak valid')


@router.post('/pick')
def pick(request: Request, response: Response, payload: PickRequest):
    spin.guard_write(request)
    validate_input(payload)
    db = open_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        acct = spin.account_from_session(request,db)
        aid = acct['id']
        duplicate=db.execute('SELECT round_id,selected_count FROM orbit_requests WHERE account_id=? AND request_id=?',
                             (aid,payload.request_id)).fetchone()
        if duplicate:
            row=db.execute('SELECT * FROM orbit_rounds WHERE id=?', (duplicate['round_id'],)).fetchone()
            db.commit()
            response.headers['Cache-Control']='no-store'
            return {'round':view_round(row,duplicate['selected_count']),
                    'account':spin.account_view(acct),'replayed':True}
        row=current_round(db,aid)
        stamp=time.time()
        if row is None:
            revision, config = economy.active(db)
            if payload.stake not in (config.stake_options if config else spin.COSTS):
                raise HTTPException(422,'Tahapan BET berubah. Muat ulang pengaturan BET.')
            promotion = None
            charged_stake = payload.stake
            if payload.auto_session_id:
                promotion = autoplay.by_id(db, aid, payload.auto_session_id)
                if not promotion:
                    raise HTTPException(409, 'Sesi AUTO tidak ditemukan')
                if promotion['stake'] != payload.stake:
                    raise HTTPException(409, 'BET AUTO tidak sesuai')
                charged_stake, _ = autoplay.round_terms(promotion)
            if acct['balance'] < charged_stake:
                raise HTTPException(409,'Koin tidak cukup. Klaim hadiah atau refill gratis.')
            cards=economy.draw(config) if config else choose_cards()
            if config:
                combo, multiplier, tier = economy.classify(cards, config)
            else:
                tier=classify_rank(cards)
                combo='COLOR_MATCH' if tier is not None else 'NO_MATCH'
                multiplier=CELEBRATIONS[tier]['multiplier'] if tier else 0
            snapshot=json.dumps({'revision':revision,'multiplier':multiplier,
                'config':config.model_dump(mode='json')}) if config else None
            rid=spin.new_id()
            db.execute('''INSERT INTO orbit_rounds
                (id,account_id,start_key,stake,charged_stake,auto_session_id,
                 cards_json,picked,combo,tier,rules_version,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                (rid,aid,payload.request_id,payload.stake,charged_stake,
                 promotion['id'] if promotion else None,
                 json.dumps(cards,separators=(',',':')),1,combo,tier,RULES_VERSION,stamp))
            db.execute('UPDATE orbit_rounds SET economy_json=? WHERE id=?',(snapshot,rid))
            new_balance=acct['balance']-charged_stake
            db.execute('UPDATE accounts SET balance=? WHERE id=?',(new_balance,aid))
            db.execute('INSERT INTO ledger(id,account_id,reason,delta,balance_after,created_at) VALUES(?,?,?,?,?,?)',
                       (spin.new_id(),aid,'auto_free_spin' if charged_stake == 0 else 'orbit_stake',
                        -charged_stake,new_balance,stamp))
            picked=1
        else:
            # The stake is fixed on spin #1. Subsequent requests cannot change it.
            if (payload.auto_session_id is not None
                    and payload.auto_session_id != row['auto_session_id']):
                raise HTTPException(409, 'Ronde sedang berjalan milik sesi lain')
            if payload.stake != row['stake']:
                raise HTTPException(409,'Biaya ronde sedang berlangsung tidak dapat diganti')
            rid=row['id']
            picked=row['picked']+1
            if picked > 3:
                raise HTTPException(409,'Ronde ini sudah selesai')
            if picked == 3:
                rank=row['tier'] or 5  # Existing v1 unfinished Color Match keeps its original award.
                if row['combo']=='COLOR_MATCH' and int(row['rules_version'])>=3:
                    if classify_rank(json.loads(row['cards_json'])) != rank:
                        raise RuntimeError('Invalid stored card/payout combination; settlement blocked')
                multiplier=CELEBRATIONS[rank]['multiplier'] if row['combo']=='COLOR_MATCH' else 0
                if row['economy_json']:
                    snap=json.loads(row['economy_json'])
                    classified=economy.classify(
                        json.loads(row['cards_json']), economy.Config.model_validate(snap['config']),
                        draw_two_match=int(row['rules_version']) >= 3)
                    if classified != (row['combo'],snap['multiplier'],row['tier']):
                        raise RuntimeError('Invalid snapshotted payout; settlement blocked')
                    multiplier=snap['multiplier']
                payout=multiplier * row['stake']
                new_balance=min(spin.COIN_CAP,acct['balance']+payout)
                credited=new_balance-acct['balance']
                db.execute('UPDATE orbit_rounds SET picked=3,payout=?,finished_at=? WHERE id=?',(credited,stamp,rid))
                db.execute('UPDATE accounts SET balance=?,spins=spins+1,color_wins=color_wins+? WHERE id=?',
                           (new_balance,int(row['combo']=='COLOR_MATCH'),aid))
                db.execute('INSERT INTO ledger(id,account_id,reason,delta,balance_after,created_at) VALUES(?,?,?,?,?,?)',
                           (spin.new_id(),aid,'orbit_payout',credited,new_balance,stamp))
                promo_coin = 0
                if row['auto_session_id']:
                    promo_session = autoplay.by_id(db, aid, row['auto_session_id'])
                    if promo_session is None:
                        raise RuntimeError('Missing Auto Play session')
                    refreshed = db.execute('SELECT * FROM accounts WHERE id=?', (aid,)).fetchone()
                    promo_coin, _ = autoplay.complete_round(db, promo_session, refreshed, stamp)
                    db.execute('UPDATE orbit_rounds SET promo_coin=? WHERE id=?',
                               (promo_coin, rid))
                    new_balance += promo_coin
                if row['charged_stake'] > 0:
                    db.execute('INSERT INTO spins(id,account_id,request_id,stake,payout,delta,balance_after,combo,cards_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                               (rid,aid,row['start_key'],row['charged_stake'],
                                credited+promo_coin,credited+promo_coin-row['charged_stake'],
                                new_balance,row['combo'],row['cards_json'],stamp))
            else:
                db.execute('UPDATE orbit_rounds SET picked=? WHERE id=?',(picked,rid))
        db.execute('INSERT INTO orbit_requests(account_id,request_id,round_id,selected_count) VALUES(?,?,?,?)',
                   (aid,payload.request_id,rid,picked))
        db.commit()
        updated=db.execute('SELECT * FROM accounts WHERE id=?',(aid,)).fetchone()
        updated_row=db.execute('SELECT * FROM orbit_rounds WHERE id=?',(rid,)).fetchone()
        response.headers['Cache-Control']='no-store'
        return {'round':view_round(updated_row,picked),'account':spin.account_view(updated),'replayed':False}
    except Exception:
        if db.in_transaction: db.rollback()
        raise
    finally:
        db.close()
