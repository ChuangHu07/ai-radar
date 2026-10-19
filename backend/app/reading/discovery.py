import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import time
from starlette.concurrency import run_in_threadpool
from ..documents.pdf import inspect_pdf
from ..errors import AppError
from ..store import identity, now
from ..sources.categories import category_members
from .overview import generate_overview, OverviewSourceError
from .language import translate_report


def public_paper(paper):
    return {key: value for key, value in paper.items() if not key.startswith('_')}


def make_material(paper, data, parsed=None):
    return {'material_id': identity(), 'revision': 1, 'filename': paper['arxiv_id'].replace('/', '-') + '.pdf',
        'original_filename': paper['title'], 'origin': 'arxiv', 'content_source': 'arxiv', 'paper_id': paper['paper_id'],
        'sha256': __import__('hashlib').sha256(data).hexdigest(), 'byte_size': len(data),
        'status': 'ready' if parsed else 'failed', 'page_count': 0, 'page_checks': [], 'warnings': [],
        'error': None if parsed else paper['error'], **(parsed or {})}


def decide(job, decisions):
    if job['kind'] != 'overview' or job['status'] != 'awaiting_decision':
        raise AppError('JOB_NOT_AWAITING_DECISION', '此任务当前不等待论文选择。', 409)
    pending = {p['paper_id']: p for p in job['_papers'] if p['acquisition_status'] == 'failed'}
    if len(decisions) != len(pending) or {d.paper_id for d in decisions} != set(pending):
        raise AppError('INCOMPLETE_DECISIONS', '请为每一篇失败论文明确选择一次继续或移除。', 422)
    if any(d.action == 'use_abstract' and not pending[d.paper_id]['summary'].strip() for d in decisions):
        raise AppError('NO_ABSTRACT', '正文和摘要均不可用，这篇只能移除或退出。', 422)
    for decision in decisions:
        paper = pending[decision.paper_id]
        paper['acquisition_status'] = 'removed' if decision.action == 'remove' else 'abstract_selected'
        paper['basis'] = None if decision.action == 'remove' else 'abstract'
    job['papers'] = [public_paper(p) for p in job['_papers']]
    job.update(status='running', phase='已确认材料，等待生成速览')
    job['_decision_event'].set()


def enqueue_overview(store, source, codes, cutoff=None, retained=None, generate=generate_overview, language='zh'):
    category_members(codes)
    cutoff = cutoff or datetime.now(timezone.utc)
    papers = deepcopy(retained) if retained is not None else []
    job = {'job_id': identity(), 'collection_id': None, 'collection_revision': None, 'kind': 'overview', 'language': language,
        'template_version': 3, 'category_codes': codes, 'cutoff_at': cutoff.isoformat().replace('+00:00', 'Z'),
        'status': 'queued', 'phase': '等待检索', 'completed_pages': 0, 'total_pages': 0,
        'report_id': None, 'error': None, 'usage': {}, 'created_at': now(), 'elapsed_seconds': None,
        'snapshot': [], 'papers': [], '_papers': papers, '_decision_event': asyncio.Event()}
    store.jobs[job['job_id']] = job

    async def run():
        started = time.monotonic()
        try:
            job.update(status='running', phase='检索 arXiv 最新论文')
            if retained is None:
                papers.extend(await source.latest(category_members(codes), cutoff))
                if not papers:
                    raise AppError('NO_PAPERS', '未找到论文。请尝试其他官方分类。', 404)
                for index, paper in enumerate(papers):
                    job['phase'] = f'获取并检查全文 · {index+1}/{len(papers)} 篇'
                    job['papers'] = [public_paper(p) for p in papers]
                    try:
                        data = await source.download(paper)
                        parsed = await run_in_threadpool(inspect_pdf, data)
                        paper['_texts'] = parsed.pop('texts')
                        paper.update(acquisition_status='ready', basis='full_pdf', _data=data,
                                     _sha256=store.fingerprint(data), _material=make_material(paper, data, parsed))
                        paper['_path'] = str(await run_in_threadpool(store.save_pdf, paper['_material']['material_id'], data))
                    except AppError as exc:
                        paper.update(acquisition_status='failed', error=exc.payload(), basis=None)
            job['papers'] = [public_paper(p) for p in papers]
            store.ensure_session()
            (store.session_dir / f'{job["job_id"]}-acquired.json').write_text(json.dumps([
                {**public_paper(p), 'material': p.get('_material'), 'path': p.get('_path'), 'sha256': p.get('_sha256')}
                for p in papers], ensure_ascii=False), encoding='utf-8')
            while True:
                if any(p['acquisition_status'] == 'failed' for p in papers):
                    job['_decision_event'].clear()
                    job.update(status='awaiting_decision', phase='请处理全文失败的论文后再生成', papers=[public_paper(p) for p in papers])
                    await job['_decision_event'].wait()
                included = [p for p in papers if p['acquisition_status'] != 'removed']
                if not included:
                    raise AppError('NO_USABLE_PAPERS', '本次论文已全部移除，没有可生成速览的材料。', 422)
                job['snapshot'] = [{'paper_id': p['paper_id'], 'arxiv_id': p['arxiv_id'], 'basis': p['basis'], 'sha256': p.get('_sha256')} for p in included]
                job['total_pages'] = sum(p.get('_material', {}).get('page_count', 0) for p in included if p['basis'] == 'full_pdf')
                try:
                    async with store.ai_lock:
                        def phase(label):
                            job.update(status='running', phase=label)
                        def artifact(label, value):
                            store.ensure_session()
                            (store.session_dir / f'{job["job_id"]}-{label}.json').write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
                        report = await generate(included, job['usage'], phase, cache=store.evidence_cache, on_artifact=artifact)
                    break
                except OverviewSourceError as exc:
                    paper = next(p for p in papers if p['paper_id'] == exc.paper_id)
                    paper.update(acquisition_status='failed', basis=None, error=exc.payload())
                    if '_material' in paper:
                        paper['_material'].update(status='failed', error=exc.payload())
            if job['status'] == 'cancelled':
                return
            report_id = identity()
            report.update(report_id=report_id, job_id=job['job_id'], created_at=now(), cutoff_at=job['cutoff_at'],
                          category_codes=codes, retrieved_count=len(papers), included_count=len(included))
            store.reports[report_id] = {'report': report}
            if language != 'zh':
                job['report_id'] = report_id
                job['phase'] = '转换速览语言'
                async with store.ai_lock:
                    translated = await translate_report(report, language, job['usage'], lambda label: job.update(phase=label), cache=store.evidence_cache)
                report_id = identity()
                translated.update(report_id=report_id, job_id=job['job_id'])
                store.reports[report_id] = {'report': translated}
            job.update(status='succeeded', phase='前沿速览已生成', report_id=report_id, completed_pages=job['total_pages'])
        except asyncio.CancelledError:
            job.update(status='cancelled', phase='已退出本次速览')
        except AppError as exc:
            job.update(status='failed', phase='速览未完成', error=exc.payload())
        except Exception as exc:
            from .provider import model_error
            job.update(status='failed', phase='速览未完成', error=model_error(exc).payload())
            from ..config import settings
            key = settings().api_key
            chain, current = [], exc
            for _ in range(5):
                if current is None:
                    break
                message = str(current)
                chain.append({'type': type(current).__name__, 'message': (message.replace(key, '[redacted]') if key else message)[:400]})
                current = current.__cause__
            store.ensure_session()
            (store.session_dir / f'{job["job_id"]}-failure.json').write_text(json.dumps(chain), encoding='utf-8')
        finally:
            job['elapsed_seconds'] = round(time.monotonic()-started, 2)

    store.tasks[job['job_id']] = asyncio.create_task(run())
    return job


def overview_collection(store, job, selected):
    if job['kind'] != 'overview' or job['status'] != 'succeeded':
        raise AppError('OVERVIEW_NOT_READY', '请在本次速览生成完成后选择论文。', 409)
    included = {p['paper_id']: p for p in job['_papers'] if p['acquisition_status'] != 'removed'}
    if not selected or len(set(selected)) != len(selected) or not set(selected) <= included.keys():
        raise AppError('INVALID_SELECTION', '请选择属于本次速览的论文，不重复添加。', 422)
    if len(selected) > 10:
        raise AppError('TOO_MANY_MATERIALS', '精读清单最多十篇。', 422)
    collection = {'collection_id': identity(), 'revision': 1, 'materials': [], 'created_at': now()}
    for pid in selected:
        paper = included[pid]
        if paper['basis'] == 'full_pdf':
            material = deepcopy(paper['_material']); material['material_id'] = identity()
            store.files[material['material_id']] = store.save_pdf(material['material_id'], paper['_data'])
        else:
            material = make_material(paper, b'')
        collection['materials'].append(material)
    store.collections[collection['collection_id']] = collection
    return store.public_collection(collection)
