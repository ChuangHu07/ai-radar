import asyncio
from datetime import datetime, timezone
import httpx
import pytest
from app.errors import AppError
from app.sources.arxiv import ArxivClient, OVERVIEW_PAPER_LIMIT, parse_feed, pdf_url
from app.sources.categories import candidates, category_members


def atom(ids, total=None, future=None):
    """Synthetic Atom fixture, never used as real application metadata."""
    future = future or set()
    entries = ''.join(f'''<entry><id>http://arxiv.org/abs/{pid}</id><title>Synthetic learning test {pid}</title>
      <published>{'2026-10-06T00:00:00Z' if pid in future else '2026-10-03T00:00:00Z'}</published>
      <updated>2026-10-06T00:00:00Z</updated><summary>Synthetic abstract</summary>
      <author><name>Test Author</name></author><category term="cs.AI"/>
      <link title="pdf" href="http://arxiv.org/pdf/{pid}"/></entry>''' for pid in ids)
    return f'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:o="http://a9.com/-/spec/opensearch/1.1/"><o:totalResults>{len(ids) if total is None else total}</o:totalResults>{entries}</feed>'.encode()


@pytest.mark.parametrize('count', [0, 5, 10])
def test_latest_actual_count_and_query(count):
    calls = []
    async def run():
        def handle(request):
            calls.append(request)
            return httpx.Response(200, content=atom([f'2610.{i:05}v1' for i in range(count)]))
        client = ArxivClient(httpx.MockTransport(handle), interval=0)
        try:
            return await client.latest(['cs.AI'], datetime(2026, 10, 4, 2, 3, 4, tzinfo=timezone.utc))
        finally:
            await client.close()
    papers = asyncio.run(run())
    assert len(papers) == min(count, OVERVIEW_PAPER_LIMIT)
    params = calls[0].url.params
    assert params['search_query'] == '(cat:cs.AI) AND submittedDate:[199101010000 TO 202610040203]'
    assert params['sortBy'] == 'submittedDate' and params['sortOrder'] == 'descending'


def test_versions_future_and_paging():
    calls = []
    async def run():
        def handle(request):
            start = int(request.url.params['start']); calls.append(start)
            rows = ['2610.00001v1', '2610.00001v2', '2610.00002v1', '2610.00002v2', '2610.00003v1', '2610.00003v2', '2610.00004v1', '2610.00004v2', '2610.00009v1', '2610.00009v2'] if start == 0 else ['2610.00010v1']
            return httpx.Response(200, content=atom(rows, 11, {'2610.00009v1', '2610.00009v2'}))
        client = ArxivClient(httpx.MockTransport(handle), interval=0)
        try:
            return await client.latest(['cs.AI'], datetime(2026, 10, 4, tzinfo=timezone.utc))
        finally:
            await client.close()
    rows = asyncio.run(run())
    assert calls == [0, 10] and len(rows) == OVERVIEW_PAPER_LIMIT
    assert len({r['paper_id'] for r in rows}) == OVERVIEW_PAPER_LIMIT
    assert '2610.00009' not in {r['paper_id'] for r in rows}
    assert next(r for r in rows if r['paper_id'] == '2610.00001')['version'] == 2


def test_source_failure_is_not_zero():
    async def run():
        client = ArxivClient(httpx.MockTransport(lambda _: httpx.Response(429)), interval=0)
        try:
            await client.latest(['cs.AI'], datetime.now(timezone.utc))
        finally:
            await client.close()
    with pytest.raises(AppError) as exc:
        asyncio.run(run())
    assert exc.value.code == 'SOURCE_UNAVAILABLE'


@pytest.mark.parametrize('url', ['https://arxiv.org.evil.example/pdf/2610.00001v1', 'https://127.0.0.1/pdf/2610.00001v1', 'https://arxiv.org/pdf/2610.00002v1', 'https://arxiv.org/pdf/2610.00001v1?redirect=x'])
def test_official_pdf_identity_only(url):
    with pytest.raises(AppError):
        pdf_url(url, '2610.00001v1')


def test_redirect_rejects_external_host():
    async def run():
        client = ArxivClient(httpx.MockTransport(lambda _: httpx.Response(302, headers={'location': 'https://example.org/paper.pdf'})), interval=0)
        try:
            await client.download({'pdf_url': 'https://arxiv.org/pdf/2610.00001v1', 'arxiv_id': '2610.00001v1'})
        finally:
            await client.close()
    with pytest.raises(AppError) as exc:
        asyncio.run(run())
    assert exc.value.code == 'SOURCE_PDF_URL_INVALID'


def test_official_candidates_and_members():
    assert candidates('AI')[0]['code'] == 'cs.AI'
    assert [row['code'] for row in candidates('cs.AI')] == ['cs.AI']
    assert category_members(['cs.AI']) == ['cs.AI']
    assert {'cs.LG', 'stat.ML'} <= {r['code'] for r in candidates('机器学习')}
    assert 'cs.AI' in category_members(['cs'])
    assert len(category_members(['cs', 'cs.AI'])) == len(category_members(['cs']))
    with pytest.raises(AppError):
        category_members(['cs.AI OR all:attack'])


def test_non_atom_and_missing_dates_fail():
    for data in [b'<html>Blocked</html>', atom(['2610.00001v1']).replace(b'<published>', b'<missing>')]:
        with pytest.raises(AppError):
            parse_feed(data)
