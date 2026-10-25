"""Read-only rules-guide metadata. Never changes RNG, settlement or configuration."""
from copy import deepcopy
from math import prod


def enrich_catalog(entries, config, tiers):
    result = deepcopy(entries)
    tier_map = {t['rank']: t for t in tiers}
    for item in result:
        key = item['id']
        if item['group'] == 'rank':
            multiplier = int(tier_map[item['rank']]['multiplier'])
            item.update(guide_max=multiplier, guide_example=multiplier,
                        guide_raw=multiplier, guide_formula='fixed', guide_cap=multiplier,
                        sampling_active=config is None or config.percentages[key] > 0)
        elif key.startswith(('PAIR_PRODUCT_', 'PAIR_SUM_')):
            product = key.startswith('PAIR_PRODUCT_')
            draw = '_DRAW_' in key
            triple = key.endswith('_TRIPLE')
            cap = config.product_cap if product else config.sum_cap
            values = [2 if str(c['face']) == '+2' else int(c['face']) for c in item['cards']]
            raw = prod(values) if product else sum(values)
            # Attainable limits of each displayed face variant, not extra prize tiers.
            maximum = ((8 if triple else 36) if product else (6 if triple else 13)) if draw else (
                (729 if triple else 648) if product else (27 if triple else 26))
            lane = 'PAIR_PRODUCT' if product else 'PAIR_SUM'
            item.update(guide_max=min(cap, maximum), guide_example=min(cap, raw),
                        guide_raw=raw, guide_cap=cap,
                        guide_formula='product' if product else 'sum',
                        sampling_active=config.percentages[lane] > 0)
        else:
            multiplier = (config.color_pair_multiplier if key == 'COLOR_PAIR'
                          else config.color_sequence_multiplier)
            item.update(guide_max=multiplier, guide_example=multiplier,
                        guide_raw=multiplier, guide_cap=multiplier, guide_formula='fixed',
                        sampling_active=config.percentages[key] > 0)
        item['guide_variable'] = item['guide_formula'] != 'fixed' and not (
            '_DRAW_' in key and key.endswith('_TRIPLE'))
    # Display ordering is separate from the five immutable settlement ranks.
    result.sort(key=lambda item: (-item['guide_max'],
        0 if item['group'] == 'rank' else 1,
        0 if '_NUMBER_' in item['id'] else 1,
        0 if item['id'].endswith('_TRIPLE') else 1, item['id']))
    for order, item in enumerate(result, 1):
        item['guide_order'] = order
    return result
