from copy import deepcopy

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.store import Store
from app.errors import AppError
from pdf_factory import pdf_bytes


def test_switching_report_language_keeps_original_and_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr('app.main.settings', lambda: Settings('test-key', 'test-model', tmp_path, 'claude'))
    async def translate(base, language, usage, phase, **options):
        output = deepcopy(base)
        output['language'] = language
        output['source_report_id'] = base['report_id']
        return output
    monkeypatch.setattr('app.main.translate_report', translate)
    store = Store()
    store.reports['base'] = {'report': {'report_id': 'base', 'language': 'zh', 'mode': 'single',
                                       'template_version': 2, 'material_snapshot': [], 'sections': []}, 'data': {}}
    with TestClient(create_app(store=store)) as client:
        path = '/api/v1/reports/base/language-jobs'
        request = {'report_language': 'en'}
        headers = {'Idempotency-Key': 'same-language-request'}
        first = client.post(path, json=request, headers=headers)
        assert first.status_code == 202
        second = client.post(path, json=request, headers=headers)
        assert second.json()['data']['job_id'] == first.json()['data']['job_id']
        job = client.get('/api/v1/jobs/' + first.json()['data']['job_id']).json()['data']
        assert job['status'] == 'succeeded'
        translated = client.get('/api/v1/reports/' + job['report_id']).json()['data']
        assert translated['language'] == 'en'
        assert translated['source_report_id'] == 'base'
        assert client.get('/api/v1/reports/base').json()['data']['language'] == 'zh'


def test_completed_language_variant_reuses_without_new_key_or_paid_call(monkeypatch,tmp_path):
    monkeypatch.setattr('app.main.settings',lambda:Settings('','test-model',tmp_path,'claude'))
    async def forbidden(*args,**kwargs):raise AssertionError('A finished variant must not call the model')
    monkeypatch.setattr('app.main.translate_report',forbidden)
    store=Store()
    base={'report_id':'base','language':'zh','mode':'single','template_version':2,'sections':[],'material_snapshot':[]}
    store.reports['base']={'report':base,'data':{}}
    store.reports['finished']={'report':{**base,'report_id':'finished','source_report_id':'base','language':'en'},'data':{}}
    with TestClient(create_app(store=store)) as client:
        response=client.post('/api/v1/reports/base/language-jobs',json={'report_language':'en'},headers={'Idempotency-Key':'reuse-finished'})
        assert response.status_code==202
        job=client.get('/api/v1/jobs/'+response.json()['data']['job_id']).json()['data']
        assert job['status']=='succeeded' and job['usage']=={}
        assert client.get('/api/v1/reports/'+job['report_id']).json()['data']['language']=='en'


def test_failed_initial_translation_retains_a_readable_chinese_report(monkeypatch, tmp_path):
    monkeypatch.setattr('app.main.settings', lambda: Settings('test-key', 'test-model', tmp_path, 'claude'))
    async def generate(data, material, usage, phase):
        return {'mode': 'single', 'language': 'zh', 'sections': [], 'evidence': [], 'facts': []}
    async def fail(*_, **options):
        raise AppError('LANGUAGE_OUTPUT_INVALID', 'synthetic translation failure', 502)
    monkeypatch.setattr('app.reading.jobs.translate_report', fail)
    with TestClient(create_app(generate=generate)) as client:
        collection = client.post('/api/v1/collections', json={}).json()['data']
        collection = client.post(f'/api/v1/collections/{collection["collection_id"]}/uploads',
            data={'expected_revision': 0}, files={'files': ('paper.pdf', pdf_bytes(), 'application/pdf')}).json()['data']
        job = client.post('/api/v1/reading-jobs', headers={'Idempotency-Key': 'translate-fail'},
            json={'collection_id': collection['collection_id'], 'expected_revision': collection['revision'],
                  'report_language': 'en'}).json()['data']
        failed = client.get('/api/v1/jobs/' + job['job_id']).json()['data']
        assert failed['status'] == 'failed'
        assert failed['report_id']
        base = client.get('/api/v1/reports/' + failed['report_id']).json()['data']
        assert base['language'] == 'zh'
