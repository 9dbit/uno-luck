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
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from . import spin
from .sound_cloud import require_admin

router = APIRouter(prefix='/api/admin/economy', tags=['virtual economy admin'])
SCALE = 1_000_000
VIRTUAL_RP_PER_COIN = 40
MIN_PUBLISH_RTP = Decimal('85')
MAX_PUBLISH_RTP = Decimal('98')
ENGINE_MODEL = 'fixed-independent-csprng-v1'
KEYS = ('NO_MATCH', 'COLOR_PAIR', 'COLOR_SEQUENCE', 'PAIR_SUM', 'PAIR_PRODUCT', 'RANK_5', 'RANK_4', 'RANK_3', 'RANK_2', 'RANK_1')

class Config(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stake_options: list[StrictInt] = Field(min_length=1, max_length=12)
    percentages: dict[str, Decimal]
    sum_cap: StrictInt = Field(ge=5, le=1000)
    product_cap: StrictInt = Field(ge=18, le=1000)
    color_pair_multiplier: StrictInt = Field(default=2, ge=1, le=24)
    color_sequence_multiplier: StrictInt = Field(default=4, ge=2, le=24)
    multipliers: list[StrictInt] = Field(min_length=5, max_length=5)  # rank 1 to 5

    @model_validator(mode='before')
    @classmethod
    def backwards_compatible(cls, value):
        if isinstance(value, dict) and isinstance(value.get('percentages'), dict):
            value = dict(value)
            percentages = dict(value['percentages'])
            percentages.setdefault('COLOR_PAIR', Decimal('0'))
            percentages.setdefault('COLOR_SEQUENCE', Decimal('0'))
            value['percentages'] = percentages
        return value

    @model_validator(mode='after')
    def valid(self):
        if self.stake_options != sorted(set(self.stake_options)) or self.stake_options[0] != 10 or self.stake_options[-1] > 25000:
            raise ValueError('BET harus terurut, unik, mulai 10 Coin (Rp400 virtual), maksimal 25.000 Coin')
        if set(self.percentages) != set(KEYS):
            raise ValueError('Sepuluh kategori peluang wajib diisi')
        values = list(self.percentages.values())
        if any(not p.is_finite() or p < 0 or p > 100 or p * 10000 != (p * 10000).to_integral_value() for p in values):
            raise ValueError('Persentase 0–100, maksimal empat angka desimal')
        if sum(values) != 100:
            raise ValueError('Total persentase harus tepat 100%')
        if any(self.percentages[k] <= self.percentages['RANK_5'] for k in ('PAIR_SUM', 'PAIR_PRODUCT')):
            raise ValueError('Peluang masing-masing bonus angka harus lebih besar daripada Lucky Color Win')
        if self.color_pair_multiplier >= self.color_sequence_multiplier:
            raise ValueError('Color Sequence harus lebih tinggi daripada Color Pair')
        if not 10000 >= self.multipliers[0] > self.multipliers[1] > self.multipliers[2] > self.multipliers[3] > self.multipliers[4] > max(self.sum_cap, self.product_cap, self.color_pair_multiplier, self.color_sequence_multiplier):
            raise ValueError('Urutan payout wajib: Rank 1 > 2 > 3 > 4 > Lucky Color Win > kedua batas bonus')
        return self

PRESET = Config(stake_options=[10,20,25,50,100,250],
    percentages={'NO_MATCH':'90.7347','COLOR_PAIR':'0','COLOR_SEQUENCE':'0',
                 'PAIR_SUM':'8.5656','PAIR_PRODUCT':'0.4','RANK_5':'0.25',
                 'RANK_4':'0.04','RANK_3':'0.008','RANK_2':'0.0015','RANK_1':'0.0002'},
    sum_cap=10, product_cap=20, multipliers=[300,150,80,40,25])

class Simulation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    config: Config
    stake: StrictInt = Field(default=10, ge=10, le=25000)
    balance: StrictInt = Field(default=1000, ge=0, le=spin.COIN_CAP)
    rounds: StrictInt = Field(default=100, ge=1, le=1000)
    seed: StrictInt = Field(default=42, ge=0, le=2**32-1)
    turnover_rp: StrictInt = Field(default=1000000, ge=1, le=10**12)
    costs_rp: StrictInt = Field(default=0, ge=0, le=10**12)
    auto_sessions: StrictInt = Field(default=0, ge=0, le=1000000)
    auto_paid_rounds: StrictInt = Field(default=10, ge=1, le=10)

class Target(BaseModel):
    model_config = ConfigDict(extra='forbid')
    config: Config
    margin_percent: Decimal = Field(ge=2, le=15)


def rtp_percent(config: Config) -> float:
    return sum(multiplier * probability for multiplier, probability in distribution(config)) * 100


def assert_publish_guardrails(config: Config) -> float:
    rtp = rtp_percent(config)
    if rtp < float(MIN_PUBLISH_RTP) or rtp > float(MAX_PUBLISH_RTP):
        raise HTTPException(
            422,
            f'RTP teoretis {rtp:.4f}% di luar batas publish '
            f'{MIN_PUBLISH_RTP}–{MAX_PUBLISH_RTP}%. Draft tetap dapat disimulasikan.',
        )
    return rtp


def target_config(payload):
    # Scale all paying categories together; preserve relative rarity and payouts.
    c = payload.config
    current = sum(Decimal(str(m)) * Decimal(str(p)) for m,p in distribution(c))
    desired = (Decimal(100)-payload.margin_percent)/100
    if current <= 0:
        raise HTTPException(422, 'Draft tidak memiliki payout untuk disesuaikan')
    factor = desired/current
    probabilities = {k:(c.percentages[k]*factor).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP) for k in KEYS if k!='NO_MATCH'}
    probabilities['NO_MATCH'] = Decimal(100)-sum(probabilities.values())
    if probabilities['NO_MATCH'] < 0:
        raise HTTPException(422, 'Target tidak dapat dicapai dengan rasio peluang dan multiplier ini')
    if any(c.percentages[k]>0 and probabilities[k]==0 for k in probabilities):
        raise HTTPException(422, 'Target membuat kategori hilang pada presisi 0,0001%. Pilih target lain')
    try:
        proposed = Config.model_validate(c.model_dump() | {'percentages': probabilities})
    except ValueError:
        raise HTTPException(422, 'Target melanggar urutan peluang bonus. Pilih target lain')
    margin = 100-sum(m*p for m,p in distribution(proposed))*100
    return dict(config=proposed.model_dump(mode='json'),requested_margin_percent=float(payload.margin_percent),
        actual_margin_percent=margin,rounding_difference_percent=margin-float(payload.margin_percent),
        note='Draft saja. Semua peluang hadiah disesuaikan proporsional; NO MATCH menjadi sisanya. BET dan multiplier tetap. Margin aktual dapat berbeda karena pembulatan.')


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


def bonus_faces(hand):
    """Render duplicated numeric twos as Draw Two without changing payout math.

    The category probability and multiplier distribution remain identical to
    ``numeric_hands``: this is a face variant of value 2, not another RNG lane.
    """
    return ['+2' if value == 2 and hand.count(2) >= 2 else str(value) for value in hand]


def classify(cards, config, *, draw_two_match=True):
    from . import orbit
    faces = [str(c.get('face')) for c in cards]
    allowed = tuple(map(str, range(10))) + (('+2',) if draw_two_match else ())
    if (len(cards) == 3 and all(f in allowed for f in faces)
            and len(set(faces)) < 3 and all(c.get('color') in spin.COLORS for c in cards)):
        values = [2 if face == '+2' else int(face) for face in faces]
        same = len({c['color'] for c in cards}) == 1
        return ('PAIR_PRODUCT', min(math.prod(values), config.product_cap), None) if same else ('PAIR_SUM', min(sum(values), config.sum_cap), None)
    rank = orbit.classify_rank(cards)
    if rank:
        return ('COLOR_MATCH', config.multipliers[rank-1], rank)
    if len(cards) == 3:
        colors = [card.get('color') for card in cards]
        numeric = set(map(str, range(10)))
        if config.percentages['COLOR_SEQUENCE'] > 0:
            for position in (0, 1):
                if (colors[position] == colors[position+1]
                        and colors[position] in spin.COLORS
                        and faces[position] in numeric
                        and faces[position+1] in numeric
                        and abs(int(faces[position])-int(faces[position+1])) == 1):
                    return ('COLOR_SEQUENCE', config.color_sequence_multiplier, None)
        if config.percentages['COLOR_PAIR'] > 0 and any(colors.count(color) >= 2 for color in spin.COLORS):
            return ('COLOR_PAIR', config.color_pair_multiplier, None)
    return ('NO_MATCH', 0, None)


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
        cards = [dict(color=c, face=face) for c,face in zip(colors, bonus_faces(hand))]
    elif key in ('COLOR_PAIR', 'COLOR_SEQUENCE'):
        for _ in range(1000):
            positions = secrets.choice(((0,1),(1,2))) if key == 'COLOR_SEQUENCE' else secrets.choice(((0,1),(0,2),(1,2)))
            i,j = positions
            shared = secrets.choice(spin.COLORS)
            different = secrets.choice(tuple(color for color in spin.COLORS if color != shared))
            colors = [different,different,different]
            colors[i] = colors[j] = shared
            if key == 'COLOR_SEQUENCE':
                a = secrets.randbelow(9)
                values = [None,None,None]
                values[i],values[j] = a,a+1
                values[3-i-j] = secrets.choice(tuple(value for value in range(10) if value not in (a,a+1)))
            else:
                values = secrets.SystemRandom().sample(range(10), 3)
            cards = [dict(color=color,face=str(value)) for color,value in zip(colors,values)]
            if classify(cards,config)[0] == key:
                break
        else:
            raise RuntimeError('Unable to generate color prize hand')
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
        if key == 'COLOR_PAIR':
            result[config.color_pair_multiplier] += p
        elif key == 'COLOR_SEQUENCE':
            result[config.color_sequence_multiplier] += p
        elif key.startswith('PAIR_'):
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
    if payload.auto_paid_rounds not in (1,3,5,10):
        raise HTTPException(422,'AUTO hanya menerima 1, 3, 5, atau 10 ronde berbayar')
    paid_per_auto_rp = payload.stake * payload.auto_paid_rounds * VIRTUAL_RP_PER_COIN
    free_per_auto_rp = 10 * payload.stake * VIRTUAL_RP_PER_COIN
    # Five fixed gifts with a randomly selected 30/50/100% value. These gifts
    # are not part of the card-game RNG or regular theoretical RTP.
    gift_min_rp = paid_per_auto_rp * 5 * .30
    gift_expected_rp = paid_per_auto_rp * 5 * (.30+.50+1.0)/3
    gift_max_rp = paid_per_auto_rp * 5
    promo_cost_min_rp = payload.auto_sessions * (gift_min_rp + free_per_auto_rp*expected)
    promo_cost_expected_rp = payload.auto_sessions * (gift_expected_rp + free_per_auto_rp*expected)
    promo_cost_max_rp = payload.auto_sessions * (gift_max_rp + free_per_auto_rp*expected)
    period_expected_surplus_rp = (1-expected) * payload.turnover_rp - promo_cost_expected_rp - payload.costs_rp
    period_worst_surplus_rp = (1-expected) * payload.turnover_rp - promo_cost_max_rp - payload.costs_rp
    break_even_turnover_rp = ((promo_cost_expected_rp + payload.costs_rp)/(1-expected)
                              if expected < 1 else None)
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
    positive_probability = sum(p for m,p in dist if m>0)
    return dict(rtp_percent=expected*100, expected_gross=expected*payload.stake,
        engine_model=ENGINE_MODEL,
        operator_margin_percent=(1-expected)*100,
        operator_expected_per_round=-((expected-1)*payload.stake),
        projection=dict(
            turnover_rp=payload.turnover_rp, expected_payout_rp=expected*payload.turnover_rp,
            gross_result_rp=(1-expected)*payload.turnover_rp, costs_rp=payload.costs_rp,
            net_result_rp=period_expected_surplus_rp,
            auto_sessions=payload.auto_sessions,
            paid_auto_turnover_rp=payload.auto_sessions*paid_per_auto_rp,
            auto_bonus_min_rp=payload.auto_sessions*gift_min_rp,
            auto_bonus_expected_rp=payload.auto_sessions*gift_expected_rp,
            auto_bonus_max_rp=payload.auto_sessions*gift_max_rp,
            free_spin_expected_payout_rp=payload.auto_sessions*free_per_auto_rp*expected,
            promotional_cost_min_rp=promo_cost_min_rp,
            promotional_cost_expected_rp=promo_cost_expected_rp,
            promotional_cost_max_rp=promo_cost_max_rp,
            period_expected_surplus_rp=period_expected_surplus_rp,
            period_worst_case_surplus_rp=period_worst_surplus_rp,
            break_even_turnover_rp=break_even_turnover_rp,
            feasible_expected_pool=period_expected_surplus_rp>=0,
            feasible_worst_case_pool=period_worst_surplus_rp>=0),
        expected_net=(expected-1)*payload.stake,
        payout_probability_percent=positive_probability*100,
        average_rounds_per_positive_payout=(1/positive_probability if positive_probability else None),
        profit_probability_percent=sum(p for m,p in dist if m>1)*100,
        break_even_probability_percent=sum(p for m,p in dist if m==1)*100,
        loss_probability_percent=sum(p for m,p in dist if m<1)*100,
        sessions=300, stopped_percent=stopped/3, average_rounds=sum(played)/300,
        average_end_balance=sum(endings)/300, p10_balance=endings[29], median_balance=endings[149], p90_balance=endings[269],
        trace=trace, distribution=[dict(multiplier=m,percent=p*100) for m,p in dist],
        warning='RTP dasar tidak mencakup 10 ronde gratis dan 5 bonus promosi. Proyeksi pool menghitung keduanya terpisah; surplus tidak dijamin. Simulasi 300 sesi hanya untuk ronde dasar.',
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
            legacy_rtp_percent=195.36 if config is None else None,
            engine_model=ENGINE_MODEL,
            publish_rtp_range=[float(MIN_PUBLISH_RTP), float(MAX_PUBLISH_RTP)])
    finally: db.close()


@router.post('/simulate')
def simulation(request: Request, response: Response, payload: Simulation):
    require_admin(request)
    response.headers['Cache-Control']='no-store'
    return simulate(payload)


@router.post('/publish')
def publish(request: Request, response: Response, payload: Publish):
    require_admin(request)
    theoretical_rtp = assert_publish_guardrails(payload.config)
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
        return dict(revision=revision,new_rounds_only=True,rtp_percent=theoretical_rtp,
                    engine_model=ENGINE_MODEL)
    finally:
        if db.in_transaction: db.rollback()
        db.close()


@router.post('/target')
def target(request: Request, response: Response, payload: Target):
    require_admin(request)
    response.headers['Cache-Control']='no-store'
    return target_config(payload)


@router.get('/performance')
def performance(request: Request, response: Response,
                days: int = Query(default=30, ge=1, le=365)):
    """Actual completed-round economics, isolated from player-facing APIs."""
    require_admin(request)
    from . import orbit
    db = orbit.open_db()
    try:
        since = time.time() - days * 86400
        row = db.execute('''SELECT COUNT(*) rounds,COUNT(DISTINCT account_id) players,
            COALESCE(SUM(stake),0) turnover,COALESCE(SUM(payout),0) payout
            FROM orbit_rounds WHERE finished_at IS NOT NULL AND finished_at>=?''', (since,)).fetchone()
        by_combo = db.execute('''SELECT combo,COUNT(*) rounds,COALESCE(SUM(stake),0) turnover,
            COALESCE(SUM(payout),0) payout FROM orbit_rounds
            WHERE finished_at IS NOT NULL AND finished_at>=?
            GROUP BY combo ORDER BY rounds DESC,combo''', (since,)).fetchall()
        revision, config = active(db)
        turnover, payout = int(row['turnover']), int(row['payout'])
        gross = turnover - payout
        response.headers['Cache-Control'] = 'no-store'
        return dict(days=days,as_of=int(time.time()),rounds=int(row['rounds']),players=int(row['players']),
            turnover_coin=turnover,payout_coin=payout,gross_coin=gross,
            turnover_rp=turnover*VIRTUAL_RP_PER_COIN,payout_rp=payout*VIRTUAL_RP_PER_COIN,
            gross_rp=gross*VIRTUAL_RP_PER_COIN,
            actual_rtp_percent=(payout/turnover*100 if turnover else None),
            active_revision=revision,
            theoretical_rtp_percent=(rtp_percent(config) if config else 195.36),
            engine_model=(ENGINE_MODEL if config else 'legacy-80-percent-gate'),
            by_combo=[dict(combo=item['combo'],rounds=int(item['rounds']),
                turnover_coin=int(item['turnover']),payout_coin=int(item['payout'])) for item in by_combo],
            note='Hanya ronde selesai dalam periode ini. Nilai aktual dapat menyimpang dari RTP teoretis, terutama pada sampel kecil.')
    finally:
        db.close()
