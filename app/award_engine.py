"""Rules v6: truthful color-pair outcomes and a complete public award catalog.

Published category weights/multipliers, ledger settlement and historical v1-v5
snapshots are unchanged. The NO_MATCH lane may only display a nonwinning hand.
"""
from __future__ import annotations

import collections
import secrets
from . import economy, spin
from .rules_guide import enrich_catalog


def color_indices(cards):
    counts = collections.Counter(c.get('color') for c in cards if isinstance(c, dict))
    return [i for i, card in enumerate(cards)
            if card.get('color') in spin.COLORS and counts[card['color']] >= 2]


def classify(cards, config, **legacy_options):
    """One prize only. Existing numeric/rank/sequence awards take precedence."""
    result = economy.classify(cards, config, **legacy_options)
    if result[0] != 'NO_MATCH':
        return result
    valid = len(cards) == 3 and all(
        (c.get('color') in spin.COLORS and str(c.get('face')) in spin.FACES)
        or (c.get('color') == 'wild' and str(c.get('face')) in ('WILD', '+4'))
        for c in cards)
    if valid and len(color_indices(cards)) >= 2:
        return ('COLOR_PAIR', config.color_pair_multiplier, None)
    return result


def draw(config):
    """Retain the selected payout lane, including its exact published weight.

    Never reroll the category when an old NO_MATCH template contains a color
    pair. Replace only that template with a genuine nonmatching hand. Existing
    zero-weight color categories stay zero-weight until an admin publishes.
    """
    cards = economy.draw(config)
    before = economy.classify(cards, config)
    after = classify(cards, config)
    if before == after:
        return cards
    if before[0] != 'NO_MATCH':
        raise RuntimeError('Unexpected change to an existing paying category')
    for _ in range(1000):
        colors = secrets.SystemRandom().sample(spin.COLORS, 3)
        replacement = [dict(color=color, face=secrets.choice(spin.FACES))
                       for color in colors]
        if classify(replacement, config)[0] == 'NO_MATCH':
            return replacement
    raise RuntimeError('Could not generate a truthful NO_MATCH hand')


def bonus_key(cards, combo):
    if combo not in ('PAIR_SUM', 'PAIR_PRODUCT'):
        return combo
    faces = [str(c.get('face')) for c in cards]
    kind = 'DRAW' if faces.count('+2') >= 2 else 'NUMBER'
    size = 'TRIPLE' if len(set(faces)) == 1 else 'PAIR'
    return f'{combo}_{kind}_{size}'


def describe(cards, combo, tier, payout):
    """Presentation metadata from settled cards only; no preview or promo wins."""
    if payout <= 0 or combo == 'NO_MATCH':
        return None
    faces = [str(c.get('face')) for c in cards]
    if combo == 'COLOR_MATCH':
        key = f"RANK_{tier['rank']}" if tier else 'COLOR_MATCH'
        matched = list(range(len(cards)))
    elif combo in ('PAIR_SUM', 'PAIR_PRODUCT'):
        key = bonus_key(cards, combo)
        matched = [i for i, face in enumerate(faces) if faces.count(face) >= 2]
    elif combo == 'COLOR_SEQUENCE':
        key, matched = combo, []
        for i in (0, 1):
            if (cards[i].get('color') == cards[i+1].get('color')
                    and faces[i].isdigit() and faces[i+1].isdigit()
                    and abs(int(faces[i])-int(faces[i+1])) == 1):
                matched = [i, i+1]
                break
    else:
        key, matched = combo, color_indices(cards)
    return dict(id=key, winning_indices=matched, color_indices=color_indices(cards))


def catalog(config, tiers):
    """Five established ranks plus ten disjoint, genuine bonus variants.

    Bonus IDs are category IDs, not a claim that their variable payouts form
    a strict rank order. No invented action-pair, near-miss or stacked prize.
    """
    examples = {
        1: [('wild', '+4')]*3, 2: [('wild', 'WILD')]*3,
        3: [('red', 'SKIP'), ('red', 'REVERSE'), ('red', '+2')],
        4: [('blue', '3'), ('blue', '4'), ('blue', '5')],
        5: [('green', '2'), ('green', '5'), ('green', '9')],
    }
    def hand(example):
        return [dict(color=c, face=f) for c, f in example]
    entries = [dict(id=f"RANK_{t['rank']}", group='rank', rank=t['rank'],
                    title=t['title'], rule=t['rule'], enabled=True,
                    payout_text=f"{t['multiplier']}× BET", cards=hand(examples[t['rank']]))
               for t in tiers]
    if config is None:
        return enrich_catalog(entries, config, tiers)
    for combo, label, cap in (
            ('PAIR_PRODUCT', 'Gold', config.product_cap),
            ('PAIR_SUM', 'Mixed', config.sum_cap)):
        for kind, size, values in (
                ('NUMBER', 'PAIR', ['3', '3', '2']),
                ('NUMBER', 'TRIPLE', ['3', '3', '3']),
                ('DRAW', 'PAIR', ['+2', '+2', '4']),
                ('DRAW', 'TRIPLE', ['+2', '+2', '+2'])):
            colors = ['blue']*3 if combo == 'PAIR_PRODUCT' else ['red', 'blue', 'green']
            title = f"{label} {'Triple' if size == 'TRIPLE' else 'Twin'} {'Draw Two' if kind == 'DRAW' else 'Number'}"
            operation = 'Perkalian' if combo == 'PAIR_PRODUCT' else 'Penjumlahan'
            entries.append(dict(
                id=f'{combo}_{kind}_{size}', group='bonus', title=title,
                rule=(('Tiga face sama' if size == 'TRIPLE' else 'Dua face sama')
                      + (' +2 (bernilai 2)' if kind == 'DRAW' else ' berupa angka')
                      + (', semua kartu sewarna.' if combo == 'PAIR_PRODUCT' else ', warna kartu tidak semuanya sama.')
                      + ' Hanya satu hadiah; produk nol sewarna menjadi Lucky Color.'),
                enabled=config.percentages[combo] > 0,
                payout_text=f'{operation} 3 nilai × BET, maks. {cap}×',
                cards=hand(list(zip(colors, values)))))
    entries.extend([
        dict(id='COLOR_SEQUENCE', group='bonus', title='Color Sequence',
             rule='Dua kartu berdampingan sewarna, angka berurutan; tidak menumpuk hadiah rank/angka.',
             enabled=config.percentages['COLOR_SEQUENCE'] > 0,
             payout_text=f'{config.color_sequence_multiplier}× BET',
             cards=hand([('blue', '4'), ('blue', '5'), ('red', '9')])),
        dict(id='COLOR_PAIR', group='bonus', title='Twin Color',
             rule='Minimal dua kartu berwarna sama. Rank, bonus angka, atau sequence yang berlaku didahulukan; satu hadiah saja.',
             enabled=True, payout_text=f'{config.color_pair_multiplier}× BET',
             cards=hand([('yellow', '1'), ('blue', '7'), ('yellow', '9')]))])
    return enrich_catalog(entries, config, tiers)
