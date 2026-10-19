import base64
import json
import struct

import pytest

from app.errors import AppError
from app.sources.rankings import ARCHIVE_SEARCH, parse_monthly_chart, read_ranking
from app.sources.categories import category_members


def chart():
    traces = []
    for i, code in enumerate(ARCHIVE_SEARCH):
        numbers = [1, i + 1, i + 1]
        traces.append({'name': code, 'legendgroup': code,
                       'hovertemplate': f'Archive={code}<br>Month=%{{x}}<br>Count=%{{y}}',
                       'x': ['2026-08-01', '2026-09-01', '2026-09-01'],
                       'y': {'dtype': 'i2', 'bdata': base64.b64encode(struct.pack('<hhh', *numbers)).decode()}})
    return 'Plotly.newPlot("category",[]); Plotly.newPlot("archive",' + json.dumps(traces) + ',{});'


def test_official_archive_repetitions_are_deduplicated_and_searchable():
    result = parse_monthly_chart(chart())
    assert result['month'] == '2026-09'
    assert len(result['groups']) == 11
    assert result['groups'][0]['count'] == len(ARCHIVE_SEARCH)
    for row in result['groups']:
        assert category_members(row['search_codes'])
    assert set(ARCHIVE_SEARCH['hep']) == {'hep-ex', 'hep-lat', 'hep-ph', 'hep-th'}
    assert 'nlin' in ARCHIVE_SEARCH['physics']


def test_changed_archive_chart_is_not_silently_ranked():
    with pytest.raises(AppError) as exc:
        parse_monthly_chart('Plotly.newPlot("archive",[],{});')
    assert exc.value.code == 'RANKING_FORMAT_CHANGED'


def test_verified_official_snapshot_has_searchable_archive_mapping(tmp_path):
    state = read_ranking(tmp_path)
    assert state['month'] == '2026-09'
    assert state['groups'][0]['code'] == 'cs'
    assert state['groups'][0]['count'] == 18427
    assert state['source_state'] == 'bundled_verified'
    assert all(category_members(row['search_codes']) for row in state['groups'])
    (tmp_path / 'ranking.json').write_text(json.dumps({'status': 'unavailable', 'auto_attempts': 3,
      'stopped': True, 'month': None, 'groups': [], 'error': 'network unavailable'}), encoding='utf-8')
    retained = read_ranking(tmp_path)
    assert retained['stopped'] is True
    assert retained['month'] == '2026-09'
    assert retained['error'] == 'network unavailable'
