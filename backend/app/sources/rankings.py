"""Read arXiv's published monthly submission chart, without executing its JS."""
import asyncio
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import struct

import httpx

from ..errors import AppError
from .categories import INDEX

SOURCE_PAGE = 'https://info.arxiv.org/about/reports/submission_category_by_year.html'
SOURCE_DATA = 'https://raw.githubusercontent.com/arXiv/arxiv-docs/develop/source/about/reports/submission_category_by_year.md'
ARCHIVE_SEARCH = {code: [code] for code, item in INDEX.items() if item['kind'] == 'archive' and code != 'nlin'}
ARCHIVE_SEARCH['physics'] = ['physics', 'nlin', 'gr-qc', 'quant-ph', 'nucl-ex', 'nucl-th']
ARCHIVE_SEARCH['hep'] = ['hep-ex', 'hep-lat', 'hep-ph', 'hep-th']
ARCHIVES = set(ARCHIVE_SEARCH)
assert all(code in INDEX for codes in ARCHIVE_SEARCH.values() for code in codes)
DEFAULT = {'status': 'idle', 'auto_attempts': 0, 'max_auto_attempts': 3, 'stopped': False,
           'month': None, 'groups': [], 'error': None, 'source_url': SOURCE_PAGE, 'fetched_at': None}


def _groups(counts):
    return sorted(({'code': code, 'count': count, 'search_codes': ARCHIVE_SEARCH[code],
                    'official_name': 'High Energy Physics' if code == 'hep' else INDEX[code]['official_name'],
                    'zh_name': '高能物理' if code == 'hep' else '物理学' if code == 'physics' else INDEX[code]['zh_name']}
                   for code, count in counts.items()), key=lambda row: (-row['count'], row['code']))


def _traces(text: str):
    decoder = json.JSONDecoder()
    for match in re.finditer(r'Plotly\.newPlot\s*\(', text):
        start = text.find('[', match.end())
        if start < 0:
            continue
        try:
            value, _ = decoder.raw_decode(text[start:])
        except ValueError:
            continue
        if isinstance(value, list) and value:
            yield value


def _numbers(encoded):
    if isinstance(encoded, list):
        return encoded
    if not isinstance(encoded, dict) or encoded.get('dtype') not in {'i1', 'i2', 'i4', 'u1', 'u2', 'u4'}:
        raise ValueError('unsupported Plotly numeric data')
    dtype = encoded['dtype']
    raw = base64.b64decode(encoded['bdata'], validate=True)
    width = int(dtype[1])
    if len(raw) % width:
        raise ValueError('invalid Plotly numeric data length')
    code = {'i1': 'b', 'i2': 'h', 'i4': 'i', 'u1': 'B', 'u2': 'H', 'u4': 'I'}[dtype]
    return [row[0] for row in struct.iter_unpack('<' + code, raw)]


def parse_monthly_chart(text: str) -> dict:
    """Archive traces repeat an already-aggregated count for each subcategory."""
    archive_plot = next((plot for plot in _traces(text)
                         if all('Archive=' in str(trace.get('hovertemplate', '')) for trace in plot)), None)
    if not archive_plot:
        raise AppError('RANKING_FORMAT_CHANGED', '官方月度图表未提供可识别的 Archive 系列。', 502)
    totals = {}
    months = set()
    for trace in archive_plot:
        code = trace.get('name')
        if code not in ARCHIVES or trace.get('legendgroup') != code:
            raise AppError('RANKING_CATEGORY_MISMATCH', f'官方排行分类 {code} 无法映射到检索目录。', 502)
        try:
            xs, ys = trace['x'], _numbers(trace['y'])
            if len(xs) != len(ys):
                raise ValueError('mismatched chart arrays')
            for month, count in zip(xs, ys):
                if not re.fullmatch(r'\d{4}-\d{2}-01', month) or not isinstance(count, int) or count < 0:
                    raise ValueError('invalid month or count')
                months.add(month)
                previous = totals.get((month, code))
                if previous is not None and previous != count:
                    raise ValueError('inconsistent repeated archive count')
                totals[month, code] = count
        except (KeyError, ValueError, TypeError, base64.binascii.Error) as exc:
            raise AppError('RANKING_FORMAT_CHANGED', '官方图表的月份或投稿数量格式已改变。', 502) from exc
    if not months or {trace['name'] for trace in archive_plot} != ARCHIVES:
        raise AppError('RANKING_CATEGORY_MISMATCH', '官方排行大类与本机 arXiv 检索目录不一致。', 502)
    month = max(months)
    if month > datetime.now(timezone.utc).strftime('%Y-%m-01'):
        raise AppError('RANKING_FORMAT_CHANGED', '官方图表含未来月份，无法作为最新月排行。', 502)
    return {'month': month[:7], 'groups': _groups({code: totals.get((month, code), 0) for code in ARCHIVES})}


def read_ranking(data_dir: Path):
    path = data_dir / 'ranking.json'
    snapshot = json.loads(Path(__file__).with_name('monthly_snapshot.json').read_text(encoding='utf-8'))
    fallback = {**DEFAULT, 'status': 'ready', 'month': snapshot['month'],
                'groups': _groups(snapshot['counts']), 'source_state': 'bundled_verified',
                'fetched_at': snapshot['verified_at']}
    if not path.exists():
        return fallback
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict) or not isinstance(value.get('auto_attempts'), int):
            raise ValueError('invalid ranking state')
        state = {**DEFAULT, **value, 'stopped': value['auto_attempts'] >= 3}
        if not state['groups']:
            return {**state, 'status': 'ready', 'month': fallback['month'], 'groups': fallback['groups'],
                    'source_state': 'bundled_verified', 'fetched_at': fallback['fetched_at']}
        return state
    except (OSError, ValueError, KeyError) as exc:
        raise AppError('RANKING_STATE_INVALID', '本机排行记录无法读取，请检查 ranking.json。', 409) from exc


def save_ranking(data_dir: Path, state: dict):
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / 'ranking.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


class RankingService:
    def __init__(self, data_dir: Path, client=None):
        self.data_dir = data_dir
        self.client = client
        self.lock = asyncio.Lock()

    def state(self):
        return read_ranking(self.data_dir)

    async def fetch(self, trigger='manual'):
        if self.lock.locked():
            raise AppError('RANKING_BUSY', '排行正在获取中。', 409)
        async with self.lock:
            state = self.state()
            if trigger == 'auto' and state['stopped']:
                return state
            if trigger == 'auto':
                state['auto_attempts'] += 1
            state['status'] = 'loading'
            save_ranking(self.data_dir, state)
            try:
                async def read(client):
                    failures = []
                    for url in (SOURCE_PAGE, SOURCE_DATA):
                        try:
                            response = await client.get(url)
                            response.raise_for_status()
                            if len(response.content) > 2_000_000:
                                raise ValueError('chart too large')
                            return parse_monthly_chart(response.text)
                        except (httpx.HTTPError, AppError, ValueError) as exc:
                            failures.append(f'{url}: {exc}')
                    raise ValueError('; '.join(failures))
                if self.client is None:
                    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                        parsed = await read(client)
                else:
                    parsed = await read(self.client)
                state.update(parsed, status='ready', error=None, source_state='live',
                             fetched_at=datetime.now(timezone.utc).isoformat(), stopped=state['auto_attempts'] >= 3)
            except (httpx.HTTPError, AppError, ValueError, UnicodeError) as exc:
                state.update(status='ready' if state['groups'] else 'unavailable', error=str(exc),
                             stopped=state['auto_attempts'] >= 3)
            save_ranking(self.data_dir, state)
            return state

    async def auto(self):
        for delay in (0, 3, 10):
            if delay:
                await asyncio.sleep(delay)
            state = self.state()
            if (state['groups'] and state.get('source_state') == 'live') or state['stopped']:
                return
            await self.fetch('auto')
