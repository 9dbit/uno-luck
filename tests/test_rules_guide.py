"""DEV-02 metadata must be honest, sortable and settlement-neutral."""
import json
import pytest
from app import orbit, economy, award_engine


def catalog(config=economy.PRESET):
    return orbit.public_rules(config)['win_catalog']


def test_default_order_and_exact_fixed_draw_limits():
    entries=catalog()
    assert len(entries)==15
    assert [e['guide_order'] for e in entries]==list(range(1,16))
    assert [e['guide_max'] for e in entries]==[300,150,80,40,25,20,20,20,10,10,10,8,6,4,2]
    by_id={e['id']:e for e in entries}
    assert by_id['PAIR_PRODUCT_DRAW_TRIPLE']['guide_max']==8
    assert by_id['PAIR_SUM_DRAW_TRIPLE']['guide_max']==6
    assert not by_id['PAIR_PRODUCT_DRAW_TRIPLE']['guide_variable']
    assert by_id['PAIR_PRODUCT_NUMBER_TRIPLE']['guide_variable']
    assert by_id['PAIR_PRODUCT_NUMBER_TRIPLE']['guide_raw']==27
    assert by_id['PAIR_PRODUCT_NUMBER_TRIPLE']['guide_example']==20


def test_sampling_is_not_the_same_as_rule_support():
    by_id={e['id']:e for e in catalog()}
    assert by_id['COLOR_PAIR']['enabled']
    assert not by_id['COLOR_PAIR']['sampling_active']
    assert not by_id['COLOR_SEQUENCE']['sampling_active']
    assert sum(e['sampling_active'] for e in by_id.values())==13
    assert 'percentages' not in json.dumps(list(by_id.values()))


def test_examples_match_settlement_for_sampled_categories():
    for entry in catalog():
        if not entry['sampling_active']:
            continue
        combo,multiplier,rank=award_engine.classify(entry['cards'],economy.PRESET)
        assert multiplier==entry['guide_example']
        assert multiplier<=entry['guide_max']
        if entry['group']=='rank':assert rank==entry['rank']


def test_guide_does_not_change_config_rng_or_money(monkeypatch):
    cfg=economy.PRESET
    original=cfg.model_dump_json()
    rtp=economy.rtp_percent(cfg)
    def forbidden(*args,**kwargs):raise AssertionError('Rules metadata must not draw cards')
    monkeypatch.setattr(award_engine,'draw',forbidden)
    a=catalog(cfg);b=catalog(cfg)
    assert a==b
    assert cfg.model_dump_json()==original
    assert economy.rtp_percent(cfg)==pytest.approx(rtp)
    assert [e['rank'] for e in a if e['group']=='rank']==[1,2,3,4,5]


def test_custom_caps_and_legacy_are_not_invented():
    cfg=economy.PRESET.model_copy(update={'product_cap':5,'sum_cap':3})
    by_id={e['id']:e for e in catalog(cfg)}
    assert by_id['PAIR_PRODUCT_DRAW_TRIPLE']['guide_max']==5
    assert by_id['PAIR_SUM_DRAW_TRIPLE']['guide_max']==3
    assert by_id['PAIR_PRODUCT_NUMBER_PAIR']['guide_example']==5
    legacy=catalog(None)
    assert len(legacy)==5
    assert [e['guide_max'] for e in legacy]==[200,80,30,10,2]
    assert all(e['sampling_active'] for e in legacy)
