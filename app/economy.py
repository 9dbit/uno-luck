"""Authenticated virtual-credit economy drafts, exact payout math and versioned publishing.

Percentages are unconditional probabilities per round, to four decimal places.
The legacy economy remains active until an administrator explicitly publishes.
"""
from __future__ import annotations
import collections
import itertools
import json
import math
import random
import secrets
import time
from decimal import Decimal
from functools import lru_cache
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from . import spin
from .sound_cloud import require_admin

router = APIRouter(prefix='/api/admin/economy', tags=['virtual economy admin'])
SCALE = 1_000_000
VIRTUAL_RP_PER_COIN = 40
KEYS = ('NO_MATCH', 'PAIR_SUM', 'PAIR_PRODUCT', 'RANK_5', 'RANK_4', 'RANK_3', 'RANK_2', 'RANK_1')

class Config(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stake_options: list[StrictInt] = Field(min_length=1, max_length=12)
    percentages: dict[str, Decimal]
    sum_cap: StrictInt = Field(ge=5, le=1000)
    product_cap: StrictInt = Field(ge=18, le=1000)
    multipliers: list[StrictInt] = Field(min_length=5, max_length=5)  # rank 1 to 5

    @model_validator(mode='after')
    def valid(self):
        if self.stake_options != sorted(set(self.stake_options)) or self.stake_options[0] != 10 or self.stake_options[-1] > 25000:
            raise ValueError('BET harus terurut, unik, mulai 10 Coin (Rp400 virtual), maksimal 25.000 Coin')
        if set(self.percentages) != set(KEYS):
            raise ValueError('Delapan kategori peluang wajib diisi')
        values = list(self.percentages.values())
        if any(not p.is_finite() or p < 0 or p > 100 or p * 10000 != (p * 10000).to_integral_value() for p in values):
            raise ValueError('Persentase 0–100, maksimal empat angka desimal')
        if sum(values) != 100:
            raise ValueError('Total persentase harus tepat 100%')
        if any(self.percentages[k] <= self.percentages['RANK_5'] for k in ('PAIR_SUM', 'PAIR_PRODUCT')):
            raise ValueError('Peluang masing-masing bonus angka harus lebih besar daripada Lucky Color Win')
        if not 10000 >= self.multipliers[0] > self.multipliers[1] > self.multipliers[2] > self.multipliers[3] > self.multipliers[4] > max(self.sum_cap, self.product_cap):
            raise ValueError('Urutan payout wajib: Rank 1 > 2 > 3 > 4 > Lucky Color Win > kedua batas bonus')
        return self

PRESET = Config(stake_options=[10,20,25,50,100,250],
    percentages=dict(zip(KEYS, ['93.359','5','1','0.5','0.1','0.03','0.01','0.001'])),
    sum_cap=10, product_cap=20, multipliers=[300,150,80,40,25])

class Simulation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    config: Config
    stake: StrictInt = Field(default=10, ge=10, le=25000)
    balance: StrictInt = Field(default=1000, ge=0, le=spin.COIN_CAP)
    rounds: StrictInt = Field(default=100, ge=1, le=1000)
    seed: StrictInt = Field(default=42, ge=0, le=2**32-1)

class Publish(BaseModel):
    model_config = ConfigDict(extra='forbid')
    config: Config
    expected_revision: StrictInt = Field(ge=0)


def schema(db):
    db.execute('''CREATE TABLE IF NOT EXISTS economy_configs (
        revision INTEGER PRIMARY KEY, config_json TEXT NOT NULL, created_at REAL NOT NULL)''')


def active(db):
    row = db.execute('SELECT revision,config_json FROM economy_configs ORDER BY revision DESC LIMIT 1').fetchone()
    return (row['revision'], Config.model_validate_json(row['config_json'])) if row else (0, None)


@lru_cache(maxsize=1)
def numeric_hands():
    # Ordered 0–9 triples, uniformly selected from exactly the qualifying pool.
    # This virtual generator permits triples (including 0), not a physical deck.
    return tuple(h for h in itertools.product(range(10), repeat=3) if len(set(h)) < 3)


def classify(cards, config):
    from . import orbit
    faces = [str(c.get('face')) for c in cards]
    if len(cards) == 3 and all(f in tuple(map(str, range(10))) for f in faces) and len(set(faces)) < 3 and all(c.get('color') in spin.COLORS for c in cards):
        same = len({c['color'] for c in cards}) == 1
        return ('PAIR_PRODUCT', min(math.prod(map(int, faces)), config.product_cap), None) if same else ('PAIR_SUM', min(sum(map(int, faces)), config.sum_cap), None)
    rank = orbit.classify_rank(cards)
    return ('COLOR_MATCH', config.multipliers[rank-1], rank) if rank else ('NO_MATCH', 0, None)


def draw(config):
    from . import orbit
    roll = secrets.randbelow(SCALE)
    key = None
    for candidate in KEYS:
        roll -= int(config.percentages[candidate] * 10000)
        if roll < 0:
            key = candidate
            break
    if key in ('PAIR_SUM', 'PAIR_PRODUCT'):
        hand = secrets.choice(numeric_hands())
        color = secrets.choice(spin.COLORS)
        colors = [color] * 3
        if key == 'PAIR_SUM':
            # Select uniformly over all 60 ordered mixed-color triples.
            colors = secrets.choice(tuple(c for c in itertools.product(spin.COLORS, repeat=3) if len(set(c)) > 1))
        cards = [dict(color=c, face=str(n)) for c,n in zip(colors, hand)]
    else:
        for _ in range(1000):
            if key == 'NO_MATCH':
                cards = [dict(color=secrets.choice(spin.COLORS),face=secrets.choice(spin.FACES)) for _ in range(3)]
            else:
                cards = orbit.cards_for_tier(int(key[-1]))
            combo, _, rank = classify(cards, config)
            if (key == 'NO_MATCH' and combo == key) or (key != 'NO_MATCH' and combo == 'COLOR_MATCH' and rank == int(key[-1])):
                break
        else:
            raise RuntimeError('No valid hand for selected category')
    return cards


def distribution(config):
    result = collections.defaultdict(float)
    for key in KEYS:
        p = float(config.percentages[key]) / 100
        if key.startswith('PAIR_'):
            counts = collections.Counter(min(sum(h),config.sum_cap) if key=='PAIR_SUM' else min(math.prod(h),config.product_cap) for h in numeric_hands())
            for multiplier, n in counts.items():
                result[multiplier] += p * n / len(numeric_hands())
        else:
            result[config.multipliers[int(key[-1])-1] if key.startswith('RANK_') else 0] += p
    return sorted(result.items())


def simulate(payload):
    config = payload.config
    if payload.stake not in config.stake_options:
        raise HTTPException(422, 'BET simulasi harus tersedia dalam tahapan BET')
    dist = distribution(config)
    expected = sum(m*p for m,p in dist)
    # Same exact multiplier distribution as generator; local seeded RNG never drives gameplay.
    rng = random.Random(payload.seed)
    multipliers, weights = zip(*dist)
    endings, played, stopped, trace = [], [], 0, []
    for session in range(300):
        balance = payload.balance
        count = 0
        if session == 0: trace = [balance]
        for _ in range(payload.rounds):
            if balance < payload.stake: break
            m = rng.choices(multipliers, weights=weights, k=1)[0]
            balance = min(spin.COIN_CAP, balance - payload.stake + payload.stake * m)
            count += 1
            if session == 0: trace.append(balance)
        endings.append(balance); played.append(count)
        stopped += count < payload.rounds
    endings.sort()
    return dict(rtp_percent=expected*100, expected_gross=expected*payload.stake,
        expected_net=(expected-1)*payload.stake,
        payout_probability_percent=sum(p for m,p in dist if m>0)*100,
        profit_probability_percent=sum(p for m,p in dist if m>1)*100,
        break_even_probability_percent=sum(p for m,p in dist if m==1)*100,
        loss_probability_percent=sum(p for m,p in dist if m<1)*100,
        sessions=300, stopped_percent=stopped/3, average_rounds=sum(played)/300,
        average_end_balance=sum(endings)/300, p10_balance=endings[29], median_balance=endings[149], p90_balance=endings[269],
        trace=trace, distribution=[dict(multiplier=m,percent=p*100) for m,p in dist],
        warning='Ekspektasi teoretis sebelum batas saldo. Simulasi 300 sesi berhenti saat saldo tidak cukup dan menerapkan batas saldo; bukan jaminan hasil.',
        inflation_warning=expected>1)


@router.get('')
def read_config(request: Request, response: Response):
    require_admin(request)
    from . import orbit
    db=orbit.open_db()
    try:
        revision, config=active(db)
        response.headers['Cache-Control']='no-store'
        return dict(revision=revision,active=config.model_dump(mode='json') if config else None,
            draft=(config or PRESET).model_dump(mode='json'),virtual_rp_per_coin=VIRTUAL_RP_PER_COIN,
            legacy_rtp_percent=195.36 if config is None else None)
    finally: db.close()


@router.post('/simulate')
def simulation(request: Request, response: Response, payload: Simulation):
    require_admin(request)
    response.headers['Cache-Control']='no-store'
    return simulate(payload)


@router.post('/publish')
def publish(request: Request, response: Response, payload: Publish):
    require_admin(request)
    from . import orbit
    db=orbit.open_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        revision,_=active(db)
        if revision != payload.expected_revision:
            raise HTTPException(409,'Konfigurasi sudah diubah admin lain. Muat ulang sebelum publish.')
        revision += 1
        db.execute('INSERT INTO economy_configs VALUES(?,?,?)',(revision,payload.config.model_dump_json(),time.time()))
        db.commit()
        response.headers['Cache-Control']='no-store'
        return dict(revision=revision,new_rounds_only=True)
    finally:
        if db.in_transaction: db.rollback()
        db.close()
