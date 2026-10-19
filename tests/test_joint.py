import time
import asyncio
import json
from types import SimpleNamespace
from fastapi.testclient import TestClient

from app.main import create_app
from app.errors import AppError
from app.reading.joint import JointDraft, checked_json, generate_joint_report, KEYS
from pdf_factory import pdf_bytes


def create(client):
    return client.post('/api/v1/collections', json={}).json()['data']


def add(client, collection, files):
    return client.post(f'/api/v1/collections/{collection["collection_id"]}/uploads',
        data={'expected_revision': collection['revision']},
        files=[('files', (name, data, 'application/pdf')) for name, data in files]).json()['data']


def start(client, collection):
    return client.post('/api/v1/reading-jobs', headers={'Idempotency-Key': str(time.time_ns())},
        json={'collection_id': collection['collection_id'], 'expected_revision': collection['revision'], 'report_language': 'zh'})


def complete(client, job):
    for _ in range(100):
        state = client.get(f'/api/v1/jobs/{job["job_id"]}').json()['data']
        if state['status'] not in {'queued', 'running'}:
            return state
        time.sleep(.01)
    raise AssertionError('job did not finish')


def test_mixed_list_modes_blocking_and_frozen_joint_pdf():
    seen = []
    async def fake_joint(items, usage, phase):
        seen.extend((m['material_id'], m['revision'], data) for m, data in items)
        return {'mode': 'joint', 'title': 'test', 'sections': [], 'evidence': [], 'facts': [],
                'warnings': [], 'coverage': {'page_count': 2, 'covered_pages': [1, 2]}}
    first, second = pdf_bytes(), pdf_bytes(pages=2)
    with TestClient(create_app(joint_generate=fake_joint)) as client:
        collection = add(client, create(client), [('a.pdf', first), ('b.pdf', second)])
        assert collection['derived_mode'] == 'joint' and collection['can_generate']
        job = start(client, collection).json()['data']
        assert job['kind'] == 'joint' and len(job['snapshot']) == 2
        finished = complete(client, job)
        assert finished['status'] == 'succeeded' and [x[2] for x in seen] == [first, second]
        report_id = finished['report_id']
        assert client.get(f'/api/v1/reports/{report_id}/pdf').status_code == 422
        for (material, data) in zip(collection['materials'], (first, second)):
            response = client.get(f'/api/v1/reports/{report_id}/pdf?material_id={material["material_id"]}')
            assert response.content == data
        kept = client.delete(f'/api/v1/collections/{collection["collection_id"]}/materials/{collection["materials"][0]["material_id"]}?expected_revision={collection["revision"]}').json()['data']
        assert kept['derived_mode'] == 'single' and kept['can_generate']
        empty = client.delete(f'/api/v1/collections/{collection["collection_id"]}/materials/{kept["materials"][0]["material_id"]}?expected_revision={kept["revision"]}').json()['data']
        assert empty['derived_mode'] is None and not empty['can_generate']


def test_failed_one_material_prevents_any_joint_generation():
    with TestClient(create_app(joint_generate=lambda *_: None)) as client:
        collection = add(client, create(client), [('good.pdf', pdf_bytes()), ('bad.pdf', b'not pdf')])
        assert collection['derived_mode'] == 'joint' and not collection['can_generate']
        assert start(client, collection).json()['error']['code'] == 'MATERIALS_NOT_READY'


def test_exactly_ten_ready_materials_is_the_capacity_boundary():
    with TestClient(create_app(joint_generate=lambda *_: None)) as client:
        collection = add(client, create(client), [(f'{index}.pdf', pdf_bytes()) for index in range(10)])
        assert len(collection['materials']) == 10
        assert collection['derived_mode'] == 'joint' and collection['can_generate']
        rejected = client.post(f'/api/v1/collections/{collection["collection_id"]}/uploads',
            data={'expected_revision': collection['revision']}, files={'files': ('extra.pdf', pdf_bytes(), 'application/pdf')})
        assert rejected.status_code == 422
        current = client.get(f'/api/v1/collections/{collection["collection_id"]}').json()['data']
        assert current['revision'] == collection['revision'] and len(current['materials']) == 10


def test_cumulative_validation_budget_blocks_new_paid_job(tmp_path, monkeypatch):
    from app.config import Settings
    ledger = tmp_path / 'validation' / 'qwen-budget.json'
    ledger.parent.mkdir()
    ledger.write_text(json.dumps({'limit_cny': 15, 'spent_cny': '14.0685457'}), encoding='utf-8')
    monkeypatch.setattr('app.main.settings', lambda: Settings('fake-key', 'qwen3.8-flash', tmp_path, 'qwen'))
    with TestClient(create_app()) as client:
        health = client.get('/api/v1/health').json()['data']
        assert health['validation_budget_remaining_cny'] == .9315
        collection = add(client, create(client), [('paper.pdf', pdf_bytes())])
        response = start(client, collection)
        assert response.status_code == 409 and response.json()['error']['code'] == 'MODEL_BUDGET_LIMIT'


def test_reconciled_budget_floor_survives_stale_ledger_write(tmp_path, monkeypatch):
    from app.config import Settings

    validation = tmp_path / 'validation'
    validation.mkdir()
    (validation / 'qwen-budget.json').write_text(json.dumps({'limit_cny': 15, 'spent_cny': '12'}), encoding='utf-8')
    (validation / 'qwen-budget-floor.json').write_text(json.dumps({'minimum_spent_cny': '14.9962009'}), encoding='utf-8')
    monkeypatch.setattr('app.main.settings', lambda: Settings('fake-key', 'qwen3.8-flash', tmp_path, 'qwen'))
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/health').json()['data']['validation_budget_remaining_cny'] == .0038
        collection = add(client, create(client), [('paper.pdf', pdf_bytes())])
        assert start(client, collection).json()['error']['code'] == 'MODEL_BUDGET_LIMIT'


def test_raised_cumulative_budget_does_not_reset_spending(tmp_path, monkeypatch):
    from app.config import Settings

    validation = tmp_path / 'validation'
    validation.mkdir()
    (validation / 'qwen-budget.json').write_text(json.dumps({'limit_cny': 100, 'spent_cny': '15.8404647'}), encoding='utf-8')
    (validation / 'qwen-budget-floor.json').write_text(json.dumps({'minimum_spent_cny': '15.8404647'}), encoding='utf-8')
    monkeypatch.setattr('app.main.settings', lambda: Settings('fake-key', 'qwen3.8-flash', tmp_path, 'qwen'))
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/health').json()['data']['validation_budget_remaining_cny'] == 84.1595


def test_raised_cumulative_budget_error_uses_current_limit(tmp_path, monkeypatch):
    from app.config import Settings

    validation = tmp_path / 'validation'
    validation.mkdir()
    (validation / 'qwen-budget.json').write_text(json.dumps({'limit_cny': 100, 'spent_cny': '99.5'}), encoding='utf-8')
    monkeypatch.setattr('app.main.settings', lambda: Settings('fake-key', 'qwen3.8-flash', tmp_path, 'qwen'))
    with TestClient(create_app()) as client:
        collection = add(client, create(client), [('paper.pdf', pdf_bytes())])
        response = start(client, collection)
        assert response.status_code == 409
        assert '100 元' in response.json()['error']['details']


def test_joint_draft_rejects_missing_column_and_fake_citations():
    sections = [{'key': key, 'narrative': '这里有一项研究结论，证据见 [E0001]，需要结合条件阅读。', 'evidence_ids': ['E0001']}
                for key in ('shared_scope', 'shared_knowledge', 'routes', 'results', 'relations', 'takeaways')]
    valid = {'title': '两篇论文的联合阅读报告', 'sections': sections, 'warnings': []}
    assert checked_json(json.dumps(valid), JointDraft, {'E0001'}).title == valid['title']
    for changed in ({**valid, 'sections': sections[:-1]},
                    {**valid, 'sections': [{**sections[0], 'evidence_ids': ['E9999']}, *sections[1:]]}):
        try:
            checked_json(json.dumps(changed), JointDraft, {'E0001'})
            raise AssertionError('invalid joint report was accepted')
        except AppError as exc:
            assert exc.code in {'MODEL_OUTPUT_INVALID', 'REPORT_QUALITY_FAILED'}


def test_joint_pipeline_reads_every_paper_before_publishing(monkeypatch):
    import app.reading.joint as joint
    read_ids = []
    async def fake_read(provider, data, material, usage, progress, **_):
        read_ids.append(material['material_id'])
        progress('source', 1, 1)
        return {'covered_pages': [1], 'notes': [{'pages': [1, 1], 'analysis': '研究问题与实验条件'}],
                'evidence': [{'evidence_id': 'E0001', 'material_id': material['material_id'],
                              'material_revision': 1, 'source_text': 'method and result under specified conditions',
                              'pdf_page_start': 1, 'pdf_page_end_inclusive': 1,
                              'verification_status': 'page_text_selected_content_requires_review'}]}
    monkeypatch.setattr(joint, 'read_evidence', fake_read)
    class Provider:
        model = 'fake'
        provider = 'qwen'
        comparison_calls = 0
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def count(self, *_): return 100
        async def format(self, system, messages, schema):
            if 'problem' in schema['properties']:
                evidence_id = 'E0001' if len(read_ids) == 1 else 'E0002'
                value = {field: f'论文给出独立的研究问题和条件，依据 [{evidence_id}]。'
                         for field in ('problem', 'concepts', 'method', 'results', 'limits')}
                value['evidence_ids'] = [evidence_id]
            else:
                Provider.comparison_calls += 1
                value = {'title': '两篇论文的联合精读与对照',
                         'sections': [{'key': key, 'narrative': '第一篇与第二篇的结果需结合各自条件阅读 [E0001] [E0002]。',
                                       'evidence_ids': ['E0001', 'E0002']} for key in KEYS],
                         'warnings': []}
                if Provider.comparison_calls == 1:
                    value['sections'][3]['narrative'] += ' 未核对的结果是 9999。'
            return SimpleNamespace(stop_reason='end_turn',
                content=[SimpleNamespace(type='text', text=json.dumps(value, ensure_ascii=False))],
                usage=SimpleNamespace(input_tokens=10, output_tokens=10,
                    cache_creation_input_tokens=0, cache_read_input_tokens=0))
    items = [({'material_id': key, 'revision': 1, 'status': 'ready', 'page_count': 1,
               'filename': key + '.pdf'}, b'%PDF-test') for key in ('paper-a', 'paper-b')]
    progress = []
    result = asyncio.run(generate_joint_report(items, {}, lambda label, done, total: progress.append((done, total)),
                                               provider_factory=Provider))
    assert read_ids == ['paper-a', 'paper-b']
    assert [section['key'] for section in result['sections']] == KEYS
    assert {e['material_id'] for e in result['evidence']} == {'paper-a', 'paper-b'}
    assert progress[-1] == (2, 2)
    assert Provider.comparison_calls == 2


def test_joint_pipeline_rejects_a_failed_page_segment(monkeypatch):
    import app.reading.joint as joint
    async def failed_read(*_args, **_kwargs):
        raise AppError('SOURCE_COVERAGE_INCOMPLETE', 'page 2 unavailable')
    monkeypatch.setattr(joint, 'read_evidence', failed_read)
    class Provider:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
    items = [({'material_id': key, 'revision': 1, 'status': 'ready', 'page_count': 2,
               'filename': key + '.pdf'}, b'%PDF-test') for key in ('paper-a', 'paper-b')]
    try:
        asyncio.run(generate_joint_report(items, {}, lambda *_: None, provider_factory=Provider))
        raise AssertionError('partial report published')
    except AppError as exc:
        assert exc.code == 'SOURCE_COVERAGE_INCOMPLETE'
