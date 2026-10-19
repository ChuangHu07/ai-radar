"""Official Atom metadata and PDF access, serialized within this process."""
import asyncio
from datetime import datetime, timezone
import re
import time
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import httpx
from dotenv import dotenv_values
from ..config import ROOT
from ..documents.pdf import MAX_BYTES
from ..errors import AppError

NS = {'a': 'http://www.w3.org/2005/Atom', 'x': 'http://arxiv.org/schemas/atom', 'o': 'http://a9.com/-/spec/opensearch/1.1/'}
ID = re.compile(r'^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v(\d+))?$')
OVERVIEW_PAPER_LIMIT = 5


def date(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamp requires timezone')
    return parsed.astimezone(timezone.utc)


def parse_feed(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise AppError('SOURCE_FORMAT_CHANGED', 'arXiv 返回了不支持的 XML 格式。', 502)
    try:
        root = ET.fromstring(data)
        if root.tag != '{http://www.w3.org/2005/Atom}feed':
            raise ValueError('not an Atom feed')
        total = int(root.findtext('o:totalResults', namespaces=NS))
        if total < 0:
            raise ValueError('negative result count')
        papers = []
        for entry in root.findall('a:entry', NS):
            text = lambda name: ' '.join((entry.findtext(name, default='', namespaces=NS) or '').split())
            uri = urlparse(text('a:id'))
            if uri.hostname not in {'arxiv.org', 'export.arxiv.org'} or not uri.path.startswith('/abs/'):
                raise ValueError('invalid arXiv identity')
            versioned = uri.path.removeprefix('/abs/')
            match = ID.fullmatch(versioned)
            if not match:
                raise ValueError('invalid arXiv ID')
            published, updated = text('a:published'), text('a:updated')
            date(published); date(updated)
            paper_id = re.sub(r'v\d+$', '', versioned)
            pdf = next((link.get('href') for link in entry.findall('a:link', NS) if link.get('title') == 'pdf'), None)
            papers.append({'paper_id': paper_id, 'arxiv_id': versioned, 'version': int(match[1] or 1),
                'title': text('a:title'), 'summary': text('a:summary'), 'published_at': published, 'updated_at': updated,
                'authors': [' '.join((a.findtext('a:name', '', NS)).split()) for a in entry.findall('a:author', NS)],
                'categories': [item.get('term') for item in entry.findall('a:category', NS)],
                'primary_category': entry.find('x:primary_category', NS).get('term') if entry.find('x:primary_category', NS) is not None else None,
                'comments': text('x:comment'), 'source_url': 'https://arxiv.org/abs/' + versioned,
                'pdf_url': pdf, 'acquisition_status': 'pending', 'basis': None, 'error': None})
        return total, papers
    except (ET.ParseError, TypeError, ValueError, AttributeError) as exc:
        raise AppError('SOURCE_FORMAT_CHANGED', 'arXiv 元数据无法解析或缺少必要日期 / 身份。', 502) from exc


def pdf_url(value, arxiv_id):
    uri = urlparse(value or '')
    # Restrict redirects to the same official paper, excluding arbitrary URLs.
    path = uri.path.removesuffix('.pdf')
    if uri.scheme not in {'http', 'https'} or uri.hostname not in {'arxiv.org', 'export.arxiv.org'} or uri.port not in {None, 80, 443} or uri.username or uri.password or uri.query or uri.fragment or path != '/pdf/' + arxiv_id:
        raise AppError('SOURCE_PDF_URL_INVALID', '论文 PDF 地址不属于该论文的 arXiv 官方来源。', 502)
    return 'https://' + uri.hostname + uri.path


class ArxivClient:
    def __init__(self, transport=None, interval=3.0):
        self.lock = asyncio.Lock()
        self.next_at = 0.0
        self.interval = interval
        contact = dotenv_values(ROOT / '.env').get('ARXIV_CONTACT', '')
        self.client = httpx.AsyncClient(timeout=30, follow_redirects=False, transport=transport,
                headers={'User-Agent': 'AI-Radar/0.1 local-research' + (f' (mailto:{contact})' if contact else '')})

    async def close(self):
        await self.client.aclose()

    async def get(self, url, params=None, limit=2_000_000):
        async with self.lock:
            await asyncio.sleep(max(0, self.next_at - time.monotonic()))
            try:
                async with self.client.stream('GET', url, params=params) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        return response.status_code, response.headers.get('location'), b''
                    if response.status_code != 200:
                        raise AppError('SOURCE_UNAVAILABLE', f'arXiv 返回 HTTP {response.status_code}，未自动重试。', 502, True)
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > limit:
                            raise AppError('PDF_TOO_LARGE' if limit == MAX_BYTES else 'SOURCE_RESPONSE_TOO_LARGE',
                                           'arXiv PDF 超过 50 MiB，请改用摘要或移除。' if limit == MAX_BYTES else '来源文件超出允许大小。', 413)
                    return response.status_code, None, bytes(data)
            except httpx.TimeoutException as exc:
                raise AppError('SOURCE_TIMEOUT', 'arXiv 请求超过 30 秒，未自动重试。', 502, True) from exc
            except httpx.HTTPError as exc:
                raise AppError('SOURCE_UNAVAILABLE', '无法连接 arXiv 官方来源，请检查网络后重试。', 502, True) from exc
            finally:
                self.next_at = time.monotonic() + self.interval

    async def latest(self, members, cutoff):
        query = '(' + ' OR '.join('cat:' + code for code in members) + f') AND submittedDate:[199101010000 TO {cutoff:%Y%m%d%H%M}]'
        found, start = {}, 0
        while len(found) < OVERVIEW_PAPER_LIMIT:
            status, _, data = await self.get('https://export.arxiv.org/api/query', params={
                'search_query': query, 'start': start, 'max_results': 10, 'sortBy': 'submittedDate', 'sortOrder': 'descending'})
            if status != 200:
                raise AppError('SOURCE_UNAVAILABLE', 'arXiv 元数据接口发生意外重定向。', 502, True)
            total, rows = parse_feed(data)
            for paper in rows:
                if date(paper['published_at']) > cutoff:
                    continue
                previous = found.get(paper['paper_id'])
                if previous is None or paper['version'] > previous['version']:
                    found[paper['paper_id']] = paper
            start += len(rows)
            if not rows or start >= total:
                break
            if start >= 30000:
                raise AppError('SOURCE_QUERY_LIMIT', 'arXiv 分页已到官方查询上限，无法确认本次完整结果。', 502)
        return sorted(found.values(), key=lambda row: (date(row['published_at']), row['paper_id']), reverse=True)[:OVERVIEW_PAPER_LIMIT]

    async def download(self, paper):
        url = pdf_url(paper['pdf_url'], paper['arxiv_id'])
        for _ in range(5):
            status, location, data = await self.get(url, limit=MAX_BYTES)
            if status == 200:
                if not data.startswith(b'%PDF-'):
                    raise AppError('PDF_UNREADABLE', 'arXiv 未返回有效 PDF 正文。', 422)
                return data
            # A relative official redirect still must preserve paper identity.
            from urllib.parse import urljoin
            url = pdf_url(urljoin(url, location or ''), paper['arxiv_id'])
        raise AppError('SOURCE_UNAVAILABLE', 'arXiv PDF 重定向次数过多。', 502)
