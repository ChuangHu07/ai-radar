"""Synthetic protocol/budget checks; no keys and no paid model requests."""
import asyncio
import json
from pathlib import Path
from decimal import Decimal
import httpx
import pytest
from app.config import Settings
from app.errors import AppError
from app.reading.provider import document_request, add_usage, complete_text, cache_model
from app.reading.qwen import QwenProvider, QwenBudget, BASE_URL, MODEL
from app.reading.qwen_evidence import checked_read, read_qwen_evidence, read_qwen_text_evidence
from pdf_factory import pdf_bytes


def config():
    return Settings("synthetic-secret", MODEL, Path("."), "qwen", BASE_URL)


def stream(usage=None, finish="stop", text='{"ok":true}'):
    events = [{"choices": [{"index": 0, "delta": {"content": text}, "finish_reason": finish}]}]
    if usage is not None: events.append({"choices": [], "usage": usage})
    return "\n\n".join("data: " + json.dumps(e) for e in events) + "\n\ndata: [DONE]\n\n"


def usage(pages=0):
    return {"prompt_tokens": 100, "completion_tokens": 50, "x_tools": {"pdf_page_parser": {"count": pages}}}


def test_native_pdf_transport_and_schema_and_cost():
    requests = []
    def handle(request):
        body = json.loads(request.content); requests.append(body)
        assert str(request.url) == BASE_URL + "/chat/completions"
        file = body["messages"][1]["content"][0]["file"]
        assert file["filename"] and file["file_data"].startswith("data:application/pdf;base64,")
        assert body["response_format"] == {"type": "json_object"}
        assert body["include_tool_usage"] and body["stream_options"]["include_usage"]
        return httpx.Response(200, text=stream(usage(2)))
    async def run():
        async with QwenProvider(config(), transport=httpx.MockTransport(handle)) as provider:
            total = {}; provider.bind_usage(total)
            response = await provider.format("read", document_request(pdf_bytes(2), "test.pdf", "test"), {"type": "object"})
            add_usage(total, response)
            assert complete_text(response) == '{"ok":true}'
            assert total["pdf_parsed_pages"] == 2
            assert total["estimated_cost_cny"] == pytest.approx(.040215)
            assert provider.budget.reserved == 0
    asyncio.run(run()); assert len(requests) == 1


def test_text_schema_and_truncation_still_charge_usage():
    def handle(request):
        assert json.loads(request.content)["response_format"]["type"] == "json_schema"
        return httpx.Response(200, text=stream(usage(), "length"))
    async def run():
        async with QwenProvider(config(), transport=httpx.MockTransport(handle)) as provider:
            total = {}; provider.bind_usage(total)
            response = await provider.format("test", [{"role": "user", "content": "test"}], {"type": "object"})
            add_usage(total, response)
            with pytest.raises(AppError, match="截断"): complete_text(response)
            assert total["output_tokens"] == 50 and total["estimated_cost_cny"] > 0
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["missing", "redirect", "wrong_pages", "malformed"])
def test_failure_no_retry_and_budget_accounting(mode):
    calls = []
    def handle(request):
        calls.append(request)
        if mode == "redirect": return httpx.Response(307, headers={"Location": "https://example.org"})
        if mode == "malformed": return httpx.Response(200, text="data: invalid-json\n\n")
        return httpx.Response(200, text=stream(None if mode == "missing" else usage(0)))
    async def run():
        async with QwenProvider(config(), transport=httpx.MockTransport(handle)) as provider:
            total = {}; provider.bind_usage(total)
            with pytest.raises(AppError) as error:
                await provider.read("test", document_request(pdf_bytes(), "test.pdf", "test"))
            assert "synthetic-secret" not in str(error.value)
            assert provider.budget.spent > 0 and provider.budget.reserved == 0
            assert provider.budget.unknown_calls == (0 if mode == "wrong_pages" else 1)
            assert total["attempted_calls"] == 1
    asyncio.run(run()); assert len(calls) == 1


def test_concurrent_budget_reservations_cannot_exceed_limit():
    async def run():
        budget = QwenBudget(1)
        results = await asyncio.gather(budget.reserve(8192, 1), budget.reserve(8192, 1), return_exceptions=True)
        assert sum(isinstance(r, Decimal) for r in results) == 1
        assert budget.calls == 1 and budget.reserved <= 1
    asyncio.run(run())


def test_call_cap_is_distinguished_from_money_limit_without_resetting_usage():
    async def run():
        budget = QwenBudget(15, max_calls=1)
        amount = await budget.reserve(128, 0)
        await budget.settle(amount, {"input_tokens": 10, "output_tokens": 10, "pdf_parsed_pages": 0})
        spent = budget.spent
        with pytest.raises(AppError, match="1 次调用上限"):
            await budget.reserve(128, 0)
        assert budget.calls == 1 and budget.spent == spent and budget.reserved == 0
    asyncio.run(run())


@pytest.mark.parametrize('props, limit', [({}, 4096), ({'issues': {'type': 'array'}}, 8192)])
def test_single_field_request_limits_combined_reasoning_and_answer(props, limit):
    def handle(request):
        body = json.loads(request.content)
        assert body['max_completion_tokens'] == limit
        assert body['thinking_budget'] == 2048
        assert body['enable_thinking'] is True and 'max_tokens' not in body
        return httpx.Response(200, text=stream(usage()))
    async def run():
        async with QwenProvider(config(), transport=httpx.MockTransport(handle)) as provider:
            await provider.format_field('one field', [{'role': 'user', 'content': 'test'}], {'type': 'object', 'properties': props})
    asyncio.run(run())


def source(quote="The experiment used 100 samples.", page=1, count=1):
    return {"analysis": "synthetic", "covered_pages": list(range(1, count+1)), "unreadable_pages": [],
        "quotes": [{"page": page, "quote": quote, "claim": "synthetic"}], "visual_notes": []}


@pytest.mark.parametrize("quote,page", [("The experiment used 101 samples.", 1),
    ("The experiment used 100 samples.", 2), ("The value was +100 samples.", 1)])
def test_quotes_do_not_match_wrong_page_number_or_sign(quote, page):
    with pytest.raises(AppError):
        checked_read(source(quote, page, 2), ["The experiment used 100 samples. The value was -100 samples.", "Another page."])


def test_whitespace_ligatures_only_and_missing_coverage_blocked():
    checked_read(source("The experiment used 100 samples."), ["The experiment\nused 100   samples."])
    value = source(); value["covered_pages"] = []
    with pytest.raises(AppError): checked_read(value, ["The experiment used 100 samples."])
    value = source(); value["unreadable_pages"] = [1]
    with pytest.raises(AppError): checked_read(value, ["The experiment used 100 samples."])


def test_qwen_chunks_preserve_all_physical_pages_and_offsets():
    class Reader:
        model = "synthetic"
        calls = 0
        async def count(self, *_): return 100
        async def read_source(self, system, messages, schema):
            from types import SimpleNamespace as NS
            from app.reading.qwen import convert_messages
            _, pages = convert_messages(messages); self.calls += 1
            value = source(count=pages); value['quotes'] = [{'quote_id': 'P1Q001', 'claim': 'synthetic'}]
            return NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(value))],
                usage=NS(input_tokens=100, output_tokens=50))
    provider = Reader()
    result = asyncio.run(read_qwen_evidence(provider, pdf_bytes(5),
        {"material_id": "test", "revision": 1, "filename": "test.pdf", "page_count": 5}, {}, lambda *_: None))
    assert provider.calls == 2 and result["covered_pages"] == [1,2,3,4,5]
    assert [e["pdf_page_start"] for e in result["evidence"]] == [1,5]
    assert all(e["verification_status"].startswith("page_text_selected") for e in result["evidence"])


def test_overview_text_reader_covers_every_page_without_sending_pdf():
    from types import SimpleNamespace as NS
    class Reader:
        model = 'synthetic'
        cache_identity = 'qwen:synthetic:text'
        calls = 0
        async def count(self, *_): return 100
        async def read_source(self, system, messages, schema):
            assert all(isinstance(m['content'], str) for m in messages)
            assert 'P1Q001' in messages[0]['content']
            self.calls += 1
            value = {'analysis': 'synthetic', 'covered_pages': [1, 2], 'unreadable_pages': [],
                     'quotes': [{'quote_id': 'P1Q001', 'claim': 'synthetic'}], 'visual_notes': []}
            return NS(stop_reason='end_turn', content=[NS(type='text', text=json.dumps(value))],
                      usage=NS(input_tokens=100, output_tokens=50))
    provider = Reader()
    result = asyncio.run(read_qwen_text_evidence(provider, pdf_bytes(2),
        {'material_id': 'test', 'revision': 1, 'filename': 'test.pdf', 'page_count': 2},
        {}, lambda *_: None))
    assert provider.calls == 1 and result['covered_pages'] == [1, 2]
    assert len(result['evidence']) == 1 and result['evidence'][0]['pdf_page_start'] == 1
    assert result['source_reader'] == 'qwen-all-extractable-pdf-text-v1'


def test_overview_text_reader_localizes_only_exact_global_chunk_pages():
    from app.reading.qwen_evidence import localize_chunk_pages
    value = {'covered_pages': list(range(41, 51)), 'unreadable_pages': [],
             'visual_notes': [{'page': 43, 'details': 'chart'}]}
    local = localize_chunk_pages(value, 40, 50)
    assert local['covered_pages'] == list(range(1, 11))
    assert local['visual_notes'][0]['page'] == 3
    assert value['covered_pages'][0] == 41
    wrong = {**value, 'covered_pages': list(range(41, 50))}
    assert localize_chunk_pages(wrong, 40, 50) is wrong


def test_quote_candidates_exclude_short_pdf_page_numbers():
    from app.reading.qwen_evidence import quote_candidates
    paragraph = 'A useful paragraph of source text. ' * 11 + '\n'
    candidates = quote_candidates([paragraph + '8', '9'])
    assert [item['quote'] for item in candidates.values()] == [paragraph]


def test_selection_uses_unchanged_local_text_and_blocks_invented_refs():
    from app.reading.qwen_evidence import checked_selection, quote_candidates
    texts = ['The experiment used -100 samples.\nSecond line.']
    candidates = quote_candidates(texts)
    value = source(); value['quotes'] = [{'quote_id': 'P1Q001', 'claim': 'synthetic'}]
    checked = checked_selection(value, texts, candidates)
    assert checked.quotes[0].quote == texts[0] and checked.quotes[0].page == 1
    value['quotes'].append({'quote_id': 'P1Q001', 'claim': 'another interpretation'})
    checked = checked_selection(value, texts, candidates)
    assert len(checked.quotes) == 1 and checked.quotes[0].claim == 'synthetic'
    value['quotes'][0]['quote_id'] = 'P2Q001'
    with pytest.raises(AppError): checked_selection(value, texts, candidates)


def test_pdf_ligature_quantity_equivalence_is_not_a_numeric_waiver():
    from app.reading.quality import quantities_in
    assert quantities_in('two, three, and ﬁve tilted angles') == {'2', '3', '5'}
    assert quantities_in('ﬁfteen tilted angles') == {'15'}
    assert '5' not in quantities_in('four tilted angles')


def test_cache_identity_separates_providers():
    from types import SimpleNamespace as NS
    assert cache_model(NS(model=MODEL, cache_identity="claude:test")) != cache_model(NS(model=MODEL, cache_identity="qwen:test"))


def test_reasoned_stages_bound_and_bill_total_output_without_publishing_reasoning():
    bodies = []
    def handle(request):
        body = json.loads(request.content); bodies.append(body)
        assert body['enable_thinking'] is True and body['thinking_budget'] == 4096
        assert body['max_completion_tokens'] == 16384 and 'max_tokens' not in body
        event = {'choices': [{'index': 0, 'delta': {'reasoning_content': 'private intermediate reasoning'}}]}
        return httpx.Response(200, text='data: ' + json.dumps(event) + '\n\n' + stream(usage(), text='{"ok":true}'))
    async def run():
        async with QwenProvider(config(), transport=httpx.MockTransport(handle)) as provider:
            response = await provider.format_reasoned('test', [{'role': 'user', 'content': 'test'}], {'type': 'object'})
            assert complete_text(response) == '{"ok":true}'
            assert response.usage.output_tokens == 50
            assert provider.budget.spent == Decimal('0.000215') and provider.budget.reserved == 0
    asyncio.run(run())
    assert len(bodies) == 1
