import time
from decimal import Decimal
from fastapi.testclient import TestClient
import pytest
from app.main import create_app
from app.errors import AppError
from app.reading.overview import parse_card, validate_batch, validate_audit, blocking_audit_issues, TAGS, OverviewSourceError, source_identity, validate_facts, validate_result_scope, validate_card_claims, measurement_values, locator_ids, annotate_locations, retain_verified_results
from app.sources.arxiv import parse_feed
from test_sources import atom
from pdf_factory import pdf_bytes


def test_numbered_layout_is_not_a_measurement_but_decimal_claims_remain_checked():
    assert measurement_values('1. 准确率为 12%。\n2. 使用 3 个模型。')=={12,3}
    assert measurement_values('1.25 percent and 2.4 percent')=={__import__('decimal').Decimal('1.25'),__import__('decimal').Decimal('2.4')}


class Source:
    def __init__(self, count=2, fail=None, summary=True, unavailable=False):
        self.rows = parse_feed(atom([f'2610.{i:05}v1' for i in range(count)]))[1]
        if not summary:
            for paper in self.rows:
                paper['summary'] = ''
        self.fail = set(fail or []); self.calls = 0; self.unavailable = unavailable

    async def latest(self, *_):
        self.calls += 1
        if self.unavailable:
            raise AppError('SOURCE_TIMEOUT', 'Synthetic timeout', 502, True)
        return self.rows

    async def download(self, paper):
        if paper['paper_id'] in self.fail:
            raise AppError('SOURCE_UNAVAILABLE', 'Synthetic PDF unavailable', 502, True)
        return pdf_bytes()

    async def close(self):
        pass


def wait(client, job, status):
    for _ in range(150):
        value = client.get(f'/api/v1/jobs/{job["job_id"]}').json()['data']
        if value['status'] in status:
            return value
        time.sleep(.01)
    raise AssertionError(value)


def start(client):
    return client.post('/api/v1/overview-jobs', json={'category_codes': ['cs.AI'], 'report_language': 'zh'}, headers={'Idempotency-Key': 'test-overview'}).json()['data']


def test_all_failed_decisions_before_any_model_and_identity_transfer():
    source = Source(fail=['2610.00000', '2610.00001']); calls = []
    async def generate(papers, *_args, **_kwargs):
        calls.append([p['basis'] for p in papers])
        return {'mode': 'overview', 'papers': [], 'synthetic_test': True}
    with TestClient(create_app(source=source, overview_generate=generate)) as client:
        job = wait(client, start(client), {'awaiting_decision'})
        assert not calls
        url = f'/api/v1/jobs/{job["job_id"]}/decisions'
        bad = client.post(url, json={'decisions': [{'paper_id': '2610.00000', 'action': 'remove'}]})
        assert bad.status_code == 422 and not calls
        assert all(p['acquisition_status'] == 'failed' for p in client.get(f'/api/v1/jobs/{job["job_id"]}').json()['data']['papers'])
        client.post(url, json={'decisions': [{'paper_id': '2610.00000', 'action': 'use_abstract'}, {'paper_id': '2610.00001', 'action': 'remove'}]})
        done = wait(client, job, {'succeeded', 'failed'})
        assert done['status'] == 'succeeded' and calls == [['abstract']] and source.calls == 1
        collection = client.post('/api/v1/collections', json={'from_overview_job_id': done['job_id'], 'selected_paper_ids': ['2610.00000']}).json()['data']
        assert collection['materials'][0]['origin'] == 'arxiv'
        assert collection['materials'][0]['status'] == 'failed' and not collection['can_generate']
        assert collection['materials'][0]['paper_id'] == '2610.00000'


def test_full_source_transfer_and_repeated_clicks():
    source = Source(count=1); calls = []
    async def generate(papers, *_args, **_kwargs):
        calls.append(True)
        return {'mode': 'overview', 'papers': [], 'synthetic_test': True}
    with TestClient(create_app(source=source, overview_generate=generate)) as client:
        job = start(client)
        duplicate = start(client)
        assert duplicate['job_id'] == job['job_id']
        done = wait(client, job, {'succeeded'})
        data = client.post('/api/v1/collections', json={'from_overview_job_id': done['job_id'], 'selected_paper_ids': ['2610.00000']}).json()['data']
        assert data['can_generate'] and data['materials'][0]['paper_id'] == '2610.00000'
        material = data['materials'][0]
        assert client.get(f'/api/v1/materials/{material["material_id"]}/pdf?revision=1').content == pdf_bytes()
        assert len(calls) == source.calls == 1


@pytest.mark.parametrize('unavailable,code', [(False, 'NO_PAPERS'), (True, 'SOURCE_TIMEOUT')])
def test_zero_and_request_failure_are_different(unavailable, code):
    async def generate(*_args, **_kwargs):
        raise AssertionError('must not call model')
    with TestClient(create_app(source=Source(count=0, unavailable=unavailable), overview_generate=generate)) as client:
        job = wait(client, start(client), {'failed'})
        assert job['error']['code'] == code and job['report_id'] is None


def test_no_abstract_cannot_continue_and_cancel_waiting():
    async def generate(*_args, **_kwargs):
        raise AssertionError('must not call model')
    with TestClient(create_app(source=Source(count=1, fail=['2610.00000'], summary=False), overview_generate=generate)) as client:
        job = wait(client, start(client), {'awaiting_decision'})
        response = client.post(f'/api/v1/jobs/{job["job_id"]}/decisions', json={'decisions': [{'paper_id': '2610.00000', 'action': 'use_abstract'}]})
        assert response.json()['error']['code'] == 'NO_ABSTRACT'
        assert client.post(f'/api/v1/jobs/{job["job_id"]}/cancel').json()['data']['status'] == 'cancelled'


def test_card_contract_and_source_ids():
    text = ''.join(f'<{tag}>Synthetic test [E0001]</{tag}>' for tag in TAGS)
    parsed = parse_card(text, [{'evidence_id': 'E0001'}])
    assert parsed['evidence_ids'] == ['E0001'] and parsed['plain'] == 'Synthetic test [E0001]'
    for invalid in [text.replace('</trick>', ''), text+'extra', text.replace('E0001', 'E9999'),
                    text.replace('<pain>', '<title>').replace('</pain>', '</title>'),
                    text.replace('<plain>Synthetic test [E0001]</plain>', '')]:
        with pytest.raises(AppError):
            parse_card(invalid, [{'evidence_id': 'E0001'}])


def test_batch_and_audit_must_cover_exact_papers():
    papers = [{'paper_id': 'a'}, {'paper_id': 'b'}]
    batch = {'clusters': [{'cluster_id': 'A', 'paper_ids': ['a']}], 'ratings': [], 'relations': [], 'reading_order': None}
    with pytest.raises(AppError):
        validate_batch(batch, papers)
    with pytest.raises(AppError):
        validate_audit({'results': [{'arxiv_id': 'a', 'pass': True, 'issues': []}]}, papers)
    with pytest.raises(AppError):
        validate_audit({'results': [{'arxiv_id': 'a', 'pass': False, 'issues': []}, {'arxiv_id': 'b', 'pass': True, 'issues': []}]}, papers)


def test_rating_uses_supported_enum_without_relaxing_bounds():
    from app.models.overview import Rating, BatchMap
    from pydantic import ValidationError
    schema = BatchMap.model_json_schema()['$defs']['Rating']['properties']['stars']
    assert schema['enum'] == [1, 2, 3, 4, 5] and 'minimum' not in schema and 'maximum' not in schema
    for value in [0, 6, '3']:
        with pytest.raises(ValidationError): Rating(arxiv_id='a', stars=value, reason='synthetic')


def test_native_unreadable_page_needs_explicit_decision():
    calls = []
    async def generate(papers, *_args, **_kwargs):
        calls.append(papers[0]['basis'])
        if len(calls) == 1:
            raise OverviewSourceError(papers[0]['paper_id'], AppError('SOURCE_COVERAGE_INCOMPLETE', 'Synthetic unreadable body page'))
        return {'mode': 'overview', 'synthetic_test': True}
    with TestClient(create_app(source=Source(count=1), overview_generate=generate)) as client:
        job = wait(client, start(client), {'awaiting_decision'})
        assert calls == ['full_pdf']
        assert job['papers'][0]['error']['code'] == 'SOURCE_COVERAGE_INCOMPLETE'
        client.post(f'/api/v1/jobs/{job["job_id"]}/decisions', json={'decisions': [{'paper_id': '2610.00000', 'action': 'use_abstract'}]})
        done = wait(client, job, {'succeeded'})
        assert calls == ['full_pdf', 'abstract'] and done['snapshot'][0]['basis'] == 'abstract'


def test_abstract_cache_identity_includes_version_and_content():
    one = {'arxiv_id': '2610.00001v1', 'basis': 'abstract', 'summary': 'original'}
    two = {**one, 'arxiv_id': '2610.00001v2'}
    three = {**one, 'summary': 'changed summary'}
    assert len({source_identity(p) for p in [one, two, three]}) == 3


def test_conditions_numbers_and_equivalent_decimal_format():
    fact = {'arxiv_id': 'a', 'evidence_ids': ['E0001'], 'key_results': [{'claim': 'score 12', 'number': '12', 'compared_to': 'baseline', 'setting': '10 tasks', 'evidence_ids': ['E0001']}]}
    evidence = [{'evidence_id': 'E0001', 'source_text': 'score 12.0 on 10 tasks'}]
    validate_facts(fact, {'paper_id': 'a'}, evidence)
    fact['key_results'][0]['setting'] = '100 tasks'
    with pytest.raises(AppError):
        validate_facts(fact, {'paper_id': 'a'}, evidence)


def test_pdf_table_label_glued_to_number_still_checks_exact_digits():
    fact = {'arxiv_id': 'a', 'evidence_ids': ['E0001'], 'key_results': [
        {'claim': 'result', 'number': '74.6', 'compared_to': None, 'setting': None, 'evidence_ids': ['E0001']}]}
    evidence = [{'evidence_id': 'E0001', 'source_text': 'trajectory selection74.6 +12.8'}]
    validate_facts(fact, {'paper_id': 'a'}, evidence)
    fact['key_results'][0]['number'] = '75.6'
    with pytest.raises(AppError):
        validate_facts(fact, {'paper_id': 'a'}, evidence)


def test_pdf_adjacent_one_decimal_table_cells_keep_exact_values():
    fact = {'arxiv_id': 'a', 'evidence_ids': ['E0001'], 'key_results': [
        {'claim': 'result', 'number': '74.6 and 12.8', 'compared_to': None, 'setting': None, 'evidence_ids': ['E0001']}]}
    evidence = [{'evidence_id': 'E0001', 'source_text': 'selection74.6 +12.815.5'}]
    validate_facts(fact, {'paper_id': 'a'}, evidence)
    fact['key_results'][0]['number'] = '74.6 and 12.9'
    with pytest.raises(AppError):
        validate_facts(fact, {'paper_id': 'a'}, evidence)


def test_pdf_empty_table_cell_and_model_ids_do_not_invent_measurements():
    assert measurement_values('GPT-4o在数据集上为0.71，Llama:405B为0.47') == {Decimal('0.71'), Decimal('0.47')}
    assert measurement_values('Gemma-2-9B 和 Qwen3-14B 降低53.6%') == {Decimal('53.6')}
    fact = {'arxiv_id': 'a', 'evidence_ids': ['E0001'], 'key_results': [
        {'claim': 'GPT-4o在测试中得分', 'number': '0.71', 'compared_to': 'Llama:405B 0.47',
         'setting': None, 'evidence_ids': ['E0001']}]}
    evidence = [{'evidence_id': 'E0001', 'source_text': 'GPT-4o - -0.71 Llama-405b 0.47'}]
    validate_facts(fact, {'paper_id': 'a'}, evidence)
    fact['key_results'][0]['number'] = '0.72'
    with pytest.raises(AppError):
        validate_facts(fact, {'paper_id': 'a'}, evidence)


def test_failed_repair_omits_only_unsupported_result_and_keeps_verified_result():
    good = {'claim': 'success', 'number': '0.71', 'compared_to': None, 'setting': None, 'evidence_ids': ['E0001']}
    bad = {'claim': 'comparison', 'number': '0.53', 'compared_to': None, 'setting': None, 'evidence_ids': ['E0001']}
    fact = {'arxiv_id': 'a', 'evidence_ids': ['E0001'], 'key_results': [good, bad]}
    evidence = [{'evidence_id': 'E0001', 'source_text': 'success 0.71'}]
    revised, removed = retain_verified_results(fact, {'paper_id': 'a'}, evidence)
    assert revised['key_results'] == [good] and removed == [bad]
    assert fact['key_results'] == [good, bad]
    assert retain_verified_results({**fact, 'key_results': [bad]}, {'paper_id': 'a'}, evidence) is None


def test_card_result_cannot_expand_to_unchecked_experiment():
    fact = {'key_results': [{'claim': 'overall success', 'number': '96.5%',
                             'compared_to': 'baseline 92.6%', 'setting': 'benchmark', 'evidence_ids': ['E0001']}]}
    validate_result_scope({'result': 'success from 92.6% to 96.5% [E0001]'}, fact)
    for result in ['success improved 18.0 points [E0001]', 'success improved 3.9 points [E0002]']:
        with pytest.raises(AppError):
            validate_result_scope({'result': result}, fact)


def test_magnitudes_signs_and_listed_document_locators():
    assert measurement_values('200 万评估对') == measurement_values('two million pairs')
    assert measurement_values('2 million pairs') == measurement_values('2e6 pairs')
    assert measurement_values('-0.5') != measurement_values('0.5')
    assert measurement_values('附录表 6、7，score 12') == measurement_values('Tables irrelevant; score 12')
    assert locator_ids('表 6、7') == {('table', '6'), ('table', '7')}
    assert locator_ids('图 7/8') == {('figure', '7'), ('figure', '8')}
    assert locator_ids('Figures A19 and A20') == {('figure', 'A19'), ('figure', 'A20')}
    assert measurement_values('4DCodeBench: 3D Geometry score 0.91, ranked eleventh') == measurement_values('score 0.91, rank 11')
    assert measurement_values('1.5M tokens, 13K steps') == measurement_values('1.5 million tokens, 13000 steps')
    assert measurement_values('1.5 m') == measurement_values('1.5 metres')
    assert measurement_values('1.5 m') != measurement_values('1.5M tokens')
    assert measurement_values('both configurations') == measurement_values('2 configurations')
    assert measurement_values('GPT Image 2.0 and Gemini 3.1 Pro reached 68.6%') == {Decimal('68.6')}
    assert measurement_values('Olmo-3-7B on MATH-500 matches about 100 RL steps') == {Decimal('100')}
    assert measurement_values('SD3.5 and FLUX.2 unconditional generation') == set()
    fact = {'arxiv_id': 'a', 'evidence_ids': ['E0001'], 'key_results': [{'claim': 'score 12', 'number': '12', 'compared_to': 'baseline', 'setting': '表 6、7，200 万样本', 'evidence_ids': ['E0001']}]}
    source = [{'evidence_id': 'E0001', 'source_text': 'Table 6: score 12.0; Table 7: two million samples'}]
    validate_facts(fact, {'paper_id': 'a'}, source)
    spaced = {'arxiv_id': 'a', 'evidence_ids': ['E0001'], 'key_results': [{'claim': 'Accuracy improved', 'number': '52.6% to 75.6%', 'compared_to': 'baseline', 'setting': 'watermark shift', 'evidence_ids': ['E0001']}]}
    validate_facts(spaced, {'paper_id': 'a'}, [{'evidence_id': 'E0001', 'source_text': 'watermark shift accuracy increases from 52 .6% to 75 .6%'}])
    fact['key_results'][0]['setting'] = '表 6、8，200 万样本'
    with pytest.raises(AppError):
        validate_facts(fact, {'paper_id': 'a'}, source)


def test_unverified_code_label_is_blocked():
    with pytest.raises(AppError):
        validate_card_claims({'tags': '方法改进｜代码可用'}, {'signals': {'code_available': None}})
    validate_card_claims({'tags': '方法改进｜代码可用性未知'}, {'signals': {'code_available': None}})
    validate_card_claims({'tags': '方法改进｜代码可用'}, {'signals': {'code_available': True}})


def test_code_availability_needs_a_link_to_this_papers_code():
    from app.reading.overview import conservative_code_signal, verified_code_link
    claim = {'signals': {'code_available': True}}
    no_link = {'basis': 'full_pdf', '_texts': ['Project page: example.org', 'Method text',
                                               'References: github.com/other/tool']}
    assert not verified_code_link(no_link)
    assert conservative_code_signal(claim, no_link)['signals']['code_available'] is None
    assert claim['signals']['code_available'] is True
    author_link = {'basis': 'full_pdf', '_texts': ['Code: github.com/author/project', 'Method text']}
    assert verified_code_link(author_link)
    assert conservative_code_signal(claim, author_link)['signals']['code_available'] is True


def test_audit_false_code_claim_keeps_raw_record_but_does_not_block():
    issue = {'check': 'C4', 'location': 'tags', 'severity': 'medium',
             'problem': '标签说代码可用性未知，但 paper_facts.signals.code_available 明确为 true。', 'fix': '改为代码可用'}
    audit = {'results': [{'arxiv_id': 'paper', 'pass': False, 'issues': [issue]}]}
    blocking, notes = blocking_audit_issues(audit, [{'arxiv_id': 'paper', 'signals': {'code_available': None}}],
                                           {'paper': {'tags': '代码可用性未知'}})
    assert blocking == {} and len(notes) == 1 and audit['results'][0]['issues'] == [issue]
    blocked, _ = blocking_audit_issues(audit, [{'arxiv_id': 'paper', 'signals': {'code_available': True}}],
                                      {'paper': {'tags': '代码可用性未知'}})
    assert blocked == {'paper': [issue]}


def test_metaphor_variety_advice_does_not_block_factual_audit():
    advice = {'check': 'C4', 'location': 'trick', 'severity': 'medium',
              'problem': '比喻素材重复。本批次两篇都使用图书馆。', 'fix': '换一个比喻'}
    factual = {'check': 'C1', 'location': 'result', 'severity': 'medium',
               'problem': '结果数字和原文不符。', 'fix': '核对数字'}
    audit = {'results': [{'arxiv_id': 'paper', 'pass': False, 'issues': [advice, factual]}]}
    blocked, notes = blocking_audit_issues(audit, [{'arxiv_id': 'paper', 'signals': {'code_available': None}}],
                                           {'paper': {'tags': '代码可用性未知'}})
    assert blocked == {'paper': [factual]}
    assert len(notes) == 1 and audit['results'][0]['issues'] == [advice, factual]


def test_second_person_style_opinion_is_not_a_factual_blocker():
    issue = {'check': 'C4', 'location': 'pain', 'severity': 'medium',
             'problem': '使用了第二人称叙事，带有主观诱导色彩。', 'fix': '改成第三人称'}
    audit = {'results': [{'arxiv_id': 'paper', 'pass': False, 'issues': [issue]}]}
    blocked, notes = blocking_audit_issues(audit, [{'arxiv_id': 'paper', 'signals': {'code_available': None}}],
                                           {'paper': {'tags': '代码可用性未知'}})
    assert blocked == {} and len(notes) == 1


def test_caption_identity_can_use_same_original_pdf_page():
    evidence = [{'evidence_id': 'E0001', 'source_text': 'score 12', 'pdf_page_start': 1, 'pdf_page_end_inclusive': 1}]
    annotate_locations({'evidence': evidence}, {'_texts': ['Table 6: score by model\nscore 12', 'Table 8: unrelated data']})
    fact = {'arxiv_id': 'a', 'evidence_ids': ['E0001'], 'key_results': [{'claim': 'score 12', 'number': '12', 'compared_to': '', 'setting': '表 6', 'evidence_ids': ['E0001']}]}
    validate_facts(fact, {'paper_id': 'a'}, evidence)
    fact['key_results'][0]['setting'] = '表 8'
    with pytest.raises(AppError):
        validate_facts(fact, {'paper_id': 'a'}, evidence)


def test_appendix_caption_must_match_actual_cited_page():
    evidence = [{'evidence_id': 'E0001', 'source_text': 'score 12', 'pdf_page_start': 1, 'pdf_page_end_inclusive': 1}]
    annotate_locations({'evidence': evidence}, {'_texts': ['Figure A19: scores\nscore 12', 'Figure A20: unrelated']})
    fact = {'arxiv_id': 'a', 'evidence_ids': ['E0001'], 'key_results': [{'claim': 'score 12', 'number': '12', 'compared_to': '', 'setting': '图 A19', 'evidence_ids': ['E0001']}]}
    validate_facts(fact, {'paper_id': 'a'}, evidence)
    fact['key_results'][0]['setting'] = '图 A20'
    with pytest.raises(AppError):
        validate_facts(fact, {'paper_id': 'a'}, evidence)


@pytest.mark.parametrize('fixed', [True, False, 'quality_resume'])
def test_s1_has_one_bounded_citation_repair_and_no_partial_publish(fixed):
    import asyncio
    import json
    from types import SimpleNamespace
    from app.reading.overview import generate_overview
    calls, phases, artifacts = [], [], {}
    def message(text):
        return SimpleNamespace(stop_reason='end_turn', content=[SimpleNamespace(type='text', text=text)], usage=SimpleNamespace(input_tokens=1, output_tokens=1))
    class Provider:
        model = 'synthetic-test-only'
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def format(self, system, messages, schema):
            if 'key_results' in schema['properties']:
                calls.append('S1')
                if len(calls) == 2:
                    assert '本次草稿及全部检查问题' in messages[0]['content']
                value = {'arxiv_id': 'a', 'work_type': {'primary': 'synthetic', 'secondary': None}, 'problem': 'synthetic', 'why_hard': 'synthetic', 'pain_scenario': None, 'core_idea': 'synthetic', 'key_mechanism': 'synthetic',
                    'key_results': [{'claim': 'score 12', 'number': '12', 'compared_to': None, 'setting': '10 tasks' if fixed and len(calls)==2 else '20 tasks', 'source': 'arxiv_abstract', 'evidence_ids': ['E0001']}],
                    'address_hint': {'direction': 'synthetic', 'route': 'synthetic', 'contribution': 'synthetic'}, 'neighbors': [], 'limitations': None, 'signals': {'code_available': None, 'venue': None, 'experiment_scale': None}, 'confidence_notes': 'synthetic', 'evidence_ids': ['E0001']}
            elif 'clusters' in schema['properties']:
                calls.append('S2')
                value = {'shared_address': {'earth': {'name': 'synthetic', 'tension': 'synthetic'}, 'country': {'name': 'synthetic', 'tension': 'synthetic'}, 'state': None}, 'map_summary': 'synthetic', 'clusters': [{'cluster_id': 'A', 'name': 'synthetic', 'what_is_happening': 'synthetic', 'paper_ids': ['a']}], 'highlights': [], 'relations': [], 'ratings': [{'arxiv_id': 'a', 'stars': 3, 'reason': 'synthetic'}], 'reading_order': ['a']}
            elif 'title' in schema['properties']:
                calls.append('S3')
                if calls.count('S3') == 4:
                    assert 'Synthetic revision 3' in messages[0]['content']
                    assert messages[0]['content'].count('synthetic unsupported assertion') == 1
                value = {tag: None for tag in TAGS}
                value['tags'] = f'Synthetic revision {calls.count("S3")} [E0001]'
            else:
                calls.append('S4')
                blocked = fixed == 'quality_resume' and calls.count('S4') <= 3
                value = {'results': [{'arxiv_id': 'a', 'pass': not blocked, 'issues': [{'check': 'synthetic', 'location': 'tags', 'problem': 'synthetic unsupported assertion', 'fix': 'synthetic remove assertion', 'severity': 'medium'}] if blocked else []}]}
            return message(json.dumps(value))
        async def read(self, system, messages):
            calls.append('S3')
            if fixed == 'quality_resume' and calls.count('S3') == 4:
                assert 'Synthetic revision 3' in messages[0]['content']
                assert messages[0]['content'].count('synthetic unsupported assertion') == 1
            return message(''.join(f'<{tag}>' + ('score 12 [E0001]' if tag == 'result' else 'Synthetic background [E0001]' if tag == 'pain' else f'Synthetic revision {calls.count("S3")} [E0001]') + f'</{tag}>' for tag in TAGS))
    paper = {'paper_id': 'a', 'arxiv_id': 'av1', 'title': 'synthetic-test-only', 'authors': [], 'categories': ['cs.AI'], 'comments': None, 'summary': 'score 12 on 10 tasks', 'source_url': 'https://arxiv.org/abs/a', 'basis': 'abstract'}
    cache, usage = {}, {}
    run = generate_overview([paper], usage, phases.append, cache=cache, on_artifact=lambda name, value: artifacts.update({name: value}), provider_factory=Provider)
    if fixed == 'quality_resume':
        with pytest.raises(AppError): asyncio.run(run)
        assert calls.count('S4') == 3 and calls.count('S3') == 3
        resumed_usage = {}
        report = asyncio.run(generate_overview([paper], resumed_usage, phases.append, cache=cache, provider_factory=Provider))
        assert report['prior_audit_rounds'] == 3 and report['audit_rounds'] == 1
        assert report['resumed_quality_review'] and 'revision 4' in report['papers'][0]['card']['tags']
        assert 'revision 1' in report['papers'][0]['card']['title']
        assert resumed_usage['calls'] == 2 and calls.count('S1') == 2 and calls.count('S2') == 0
    elif fixed:
        report = asyncio.run(run)
        assert report['papers'][0]['card']['evidence_ids'] == ['E0001']
        assert calls == ['S1', 'S1', 'S3', 'S4'] and usage['calls'] == 4
        assert not any(key[-1] == 'rejected' for key in cache)
        reused_usage = {}
        again = asyncio.run(generate_overview([paper], reused_usage, phases.append, cache=cache, provider_factory=Provider))
        assert reused_usage['calls'] == 1 and calls[-1] == 'S4'
        assert again['papers'][0]['card'] == report['papers'][0]['card']
    else:
        with pytest.raises(AppError): asyncio.run(run)
        assert calls == ['S1', 'S1'] and usage['calls'] == 2
        assert 'S1-rejected-a-attempt-2' in artifacts
    assert 'request-S1-a-response' in artifacts and 'request-S1-a-repair-1-response' in artifacts


def test_repair_cannot_overwrite_other_sections_or_add_fake_reference():
    from app.reading.overview import merge_card_patch
    evidence = [{'evidence_id': 'E0001'}]
    card = parse_card(''.join(f'<{tag}>Original {tag} [E0001]</{tag}>' for tag in TAGS), evidence)
    patch = {tag: None for tag in TAGS}
    patch['result'] = 'Corrected comparison conditions [E0001]'
    changed = merge_card_patch(card, patch, {'result'}, evidence)
    assert all(changed[tag] == card[tag] for tag in TAGS if tag != 'result')
    assert changed['result'] == patch['result']
    patch['title'] = 'Unexpected new claim'
    scoped = merge_card_patch(card, patch, {'result'}, evidence)
    assert scoped['title'] == card['title']
    assert scoped['result'] == patch['result']
    patch['title'] = None; patch['result'] = 'Unsupported [E9999]'
    with pytest.raises(AppError): merge_card_patch(card, patch, {'result'}, evidence)


def test_result_condition_needs_its_own_citation_even_if_elsewhere_in_card():
    from app.reading.overview import extract_card_fields, merge_card_patch
    evidence = [
        {'evidence_id': 'E0001', 'source_text': 'A score of 37.6 percent.'},
        {'evidence_id': 'E0002', 'source_text': 'The experiment uses a 72-hour photoperiod.'},
    ]
    raw = ''.join(f'<{tag}>' + ('72 hours; score 37.6 percent [E0001]' if tag == 'result'
        else 'Synthetic text [E0002]') + f'</{tag}>' for tag in TAGS)
    with pytest.raises(AppError, match='72'):
        parse_card(raw, evidence)
    draft = extract_card_fields(raw, evidence)
    patch = {tag: None for tag in TAGS}
    patch['result'] = '72 hours [E0002]; score 37.6 percent [E0001]'
    repaired = merge_card_patch(draft, patch, {'result'}, evidence)
    assert all(repaired[tag] == draft[tag] for tag in TAGS if tag != 'result')
    patch['result'] = '73 hours [E0002]; score 37.6 percent [E0001]'
    with pytest.raises(AppError, match='73'):
        merge_card_patch(draft, patch, {'result'}, evidence)


def test_explicit_citation_lists_can_be_split_without_relaxing_checks():
    from app.reading.overview import canonicalize_citations
    evidence = [{'evidence_id': 'E0001', 'source_text': 'score 12'},
                {'evidence_id': 'E0002', 'source_text': '10 tasks'}]
    raw = ''.join(f'<{tag}>' + ('score 12 on 10 tasks [E0001, E0002]' if tag == 'result'
                               else 'Unchanged [E0001]') + f'</{tag}>' for tag in TAGS)
    fixed = canonicalize_citations(raw, evidence)
    assert fixed == raw.replace('[E0001, E0002]', '[E0001][E0002]')
    assert parse_card(fixed, evidence)['result'] == 'score 12 on 10 tasks [E0001][E0002]'
    with pytest.raises(AppError):
        canonicalize_citations(raw.replace('E0002]', 'E9999]'), evidence)
    with pytest.raises(AppError):
        parse_card(fixed.replace('score 12', 'score 13'), evidence)
    assert canonicalize_citations('[E0001–E0002]', evidence) == '[E0001–E0002]'


def test_audit_repair_uses_explicit_fix_field_if_location_is_mislabeled():
    from app.reading.overview import audit_repair_fields
    assert audit_repair_fields({'location': 'tags', 'problem': 'Simulation scope',
                               'fix': '将 plain 中的表述明确限定为仿真。'}) == {'plain'}
    assert audit_repair_fields({'location': 'result', 'problem': '标题使用错误数字',
                               'fix': '补齐条件'}) == {'title'}
    assert audit_repair_fields({'location': 'pain', 'problem': 'Unsupported claim',
                               'fix': 'Remove unsupported clause'}) == {'pain'}


def test_clinical_background_percentage_cannot_borrow_uncited_upper_bound():
    evidence = [{'evidence_id': 'E0001', 'source_text': 'Model wakefulness remains at 85%–95%.'},
                {'evidence_id': 'E0002', 'source_text': 'An index is bounded by 100%.'}]
    raw = ''.join(f'<{tag}>' + ('85%-100% [E0001]' if tag == 'pain' else 'Synthetic [E0002]') + f'</{tag}>' for tag in TAGS)
    with pytest.raises(AppError, match='100'):
        parse_card(raw, evidence)


def test_legacy_initial_draft_cannot_be_mistaken_for_audited_revision():
    import json
    import hashlib
    from app.reading.overview import validate_checkpoint
    evidence = [{'evidence_id': 'E0001'}]
    cards = {'a': parse_card(''.join(f'<{tag}>Synthetic [E0001]</{tag}>' for tag in TAGS), evidence)}
    batch = {'shared_address': {'earth': {'name': 'synthetic', 'tension': 'synthetic'}, 'country': {'name': 'synthetic', 'tension': 'synthetic'}, 'state': None}, 'map_summary': 'synthetic', 'clusters': [{'cluster_id': 'A', 'name': 'synthetic', 'what_is_happening': 'synthetic', 'paper_ids': ['a']}], 'highlights': [], 'relations': [], 'ratings': [{'arxiv_id': 'a', 'stars': 3, 'reason': 'synthetic'}], 'reading_order': None}
    sha = hashlib.sha256(json.dumps(cards,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    checkpoint = {'cards': cards, 'batch': batch, 'history': [{'results': [{'arxiv_id': 'a', 'pass': True, 'issues': []}]}], 'cards_sha256': sha}
    with pytest.raises(AppError): validate_checkpoint(checkpoint, [{'paper_id':'a'}], {'a':{'evidence':evidence}})
    checkpoint['audited_cards_sha256'] = sha
    validate_checkpoint(checkpoint, [{'paper_id':'a'}], {'a':{'evidence':evidence}})
    cards['a']['title'] = 'Changed after audit'
    with pytest.raises(AppError): validate_checkpoint(checkpoint, [{'paper_id':'a'}], {'a':{'evidence':evidence}})
