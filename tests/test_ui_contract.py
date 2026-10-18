"""Basic DOM/CSS regressions for UNO LUCK's responsive safe layout."""
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / 'app' / 'static'
HTML = (STATIC / 'index.html').read_text()
CSS = (STATIC / 'style.css').read_text()


def test_lobby_artwork_has_no_second_logo_over_the_portrait():
    assert '<h1 class="sr-only">UNO LUCK interactive card game</h1>' in HTML
    assert 'hero-gradient' not in HTML


def test_game_status_has_separate_in_flow_row():
    assert '<div class="table-status-row" aria-label="Status meja">' in HTML
    assert 'table-status-row .round-event{position:static' in CSS
    assert 'table-status-row .color-indicator{position:static' in CSS


def test_mobile_panels_and_effects_do_not_protrude_outside_viewport():
    assert '.arena{min-height:0;padding:17px 8px 13px;overflow:hidden}' in CSS
    assert '.my-panel{margin:4px 8px 16px}' in CSS
    assert '.dialog{width:min(92vw,485px)' in CSS


def test_long_player_names_can_shrink_without_covering_status():
    assert '.waiting-member strong{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' in CSS
    assert '.my-player strong{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}' in CSS
