from contextlib import asynccontextmanager
import asyncio
from copy import deepcopy
from pathlib import Path
import json
from decimal import Decimal, InvalidOperation
import uuid
from fastapi import FastAPI, Request, UploadFile, File, Form, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from .config import ROOT, settings
from .documents.pdf import inspect_pdf, MAX_BYTES
from .errors import AppError
from .models.contracts import ReadingRequest
from .store import Store, identity, now
from .reading.jobs import enqueue
from .reading.language import translate_report
from .sources.arxiv import ArxivClient, date
from .sources.categories import candidates, category_members
from .sources.rankings import RankingService
from .user_settings import read_settings, update_settings
from .models.overview import OverviewRequest, Decisions, CollectionRequest
from .reading.discovery import enqueue_overview, decide, overview_collection


class SettingsUpdate(BaseModel):
    expected_revision: int
    custom_categories: list[str] | None = None
    ui_language: str | None = None
    report_language: str | None = None


class LanguageRequest(BaseModel):
    report_language: str


def create_app(store=None, generate=None, source=None, overview_generate=None, joint_generate=None):
    store = store or Store()
    source = source or ArxivClient()
    rankings = RankingService(settings().data_dir)
    @asynccontextmanager
    async def lifespan(_):
        await run_in_threadpool(store.cleanup_stale_sessions)
        ranking_task = asyncio.create_task(rankings.auto())
        yield
        ranking_task.cancel()
        try:
            await ranking_task
        except asyncio.CancelledError:
            pass
        await store.close()
        await source.close()
    app = FastAPI(title="AI Radar", lifespan=lifespan)
    app.state.store = store

    def validation_budget_status():
        config = settings()
        if config.provider != 'qwen':
            return None
        ledger = config.data_dir / 'validation' / 'qwen-budget.json'
        floor = config.data_dir / 'validation' / 'qwen-budget-floor.json'
        if not ledger.exists():
            return None
        try:
            values = json.loads(ledger.read_text(encoding='utf-8'))
            limit = Decimal(str(values['limit_cny']))
            spent = Decimal(str(values['spent_cny']))
            if floor.exists():
                floor_values = json.loads(floor.read_text(encoding='utf-8'))
                spent = max(spent, Decimal(str(floor_values['minimum_spent_cny'])))
            if not limit.is_finite() or not spent.is_finite() or limit <= 0 or spent < 0:
                raise ValueError('invalid budget values')
            return {"limit_cny": float(limit), "remaining_cny": round(float(limit - spent), 4)}
        except (OSError, ValueError, KeyError, TypeError, InvalidOperation) as exc:
            raise AppError('BUDGET_LEDGER_INVALID', '本机费用记录无法核对，已停止新的模型任务。', 409) from exc

    def ensure_validation_budget():
        budget = validation_budget_status()
        if budget is not None and budget['remaining_cny'] < 1:
            raise AppError('MODEL_BUDGET_LIMIT', f"{budget['limit_cny']:g} 元开发验证预算仅余约 ¥{budget['remaining_cny']:.4f}；为避免开启无法完成的全文任务，已停止新调用。", 409)

    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    def result(request, data):
        return {"data": data, "request_id": request.state.request_id}

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse({"error": exc.payload(), "request_id": request.state.request_id}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def bad_request(request, _):
        return JSONResponse({"error": AppError("INVALID_REQUEST", "请求参数不完整或格式错误。").payload(), "request_id": request.state.request_id}, status_code=422)

    @app.get("/api/v1/health")
    async def health(request: Request):
        config = settings()
        return result(request, {"status": "ok", "api_version": "v1", "session_id": store.session_id, "model": config.model,
                                "provider": config.provider, "model_configured": bool(config.api_key),
                                "validation_budget_remaining_cny": (validation_budget_status() or {}).get('remaining_cny'), "slice": 3})

    @app.get('/api/v1/categories')
    async def categories(request: Request, q: str = ''):
        return result(request, candidates(q))

    @app.get('/api/v1/settings')
    async def get_settings(request: Request):
        return result(request, await run_in_threadpool(read_settings, settings().data_dir))

    @app.patch('/api/v1/settings')
    async def patch_settings(request: Request, body: SettingsUpdate):
        return result(request, await run_in_threadpool(update_settings, settings().data_dir,
                                                       body.expected_revision, body.custom_categories,
                                                       body.ui_language, body.report_language))

    @app.get('/api/v1/rankings')
    async def get_rankings(request: Request):
        return result(request, rankings.state())

    @app.post('/api/v1/rankings/fetch')
    async def fetch_rankings(request: Request):
        return result(request, await rankings.fetch('manual'))

    @app.post('/api/v1/overview-jobs', status_code=202)
    async def overview(request: Request, body: OverviewRequest, idempotency_key: str = Header(...)):
        category_members(body.category_codes)
        fingerprint = 'overview:' + store.fingerprint(body.model_dump_json().encode())
        if idempotency_key in store.idempotency:
            previous, job_id = store.idempotency[idempotency_key]
            if previous != fingerprint:
                raise AppError('IDEMPOTENCY_CONFLICT', '请求标识已经用于其他操作。', 409)
            return result(request, store.public_job(find_job(job_id)))
        if not overview_generate and not settings().api_key:
            raise AppError('MODEL_NOT_CONFIGURED', '请先在本机 .env 配置所选模型的 API Key。', 409)
        if not overview_generate:
            ensure_validation_budget()
        existing = next((j for j in store.jobs.values() if j['kind'] == 'overview' and j['category_codes'] == body.category_codes and j['language'] == body.report_language and j['status'] in {'queued', 'running', 'awaiting_decision'}), None)
        job = existing or enqueue_overview(store, source, body.category_codes, language=body.report_language, **({'generate': overview_generate} if overview_generate else {}))
        store.idempotency[idempotency_key] = fingerprint, job['job_id']
        return result(request, store.public_job(job))

    @app.post('/api/v1/jobs/{job_id}/decisions', status_code=202)
    async def decisions(request: Request, job_id: str, body: Decisions):
        job = find_job(job_id)
        decide(job, body.decisions)
        return result(request, store.public_job(job))

    @app.post("/api/v1/collections")
    async def new_collection(request: Request, body: CollectionRequest):
        if body.from_overview_job_id:
            return result(request, await run_in_threadpool(overview_collection, store, find_job(body.from_overview_job_id), body.selected_paper_ids))
        if body.selected_paper_ids:
            raise AppError('INVALID_SELECTION', '选择论文时需要提供所属的速览任务。', 422)
        collection = {"collection_id": identity(), "revision": 0, "materials": [], "created_at": now()}
        store.collections[collection["collection_id"]] = collection
        return result(request, store.public_collection(collection))

    @app.get("/api/v1/collections/{collection_id}")
    async def get_collection(request: Request, collection_id: str):
        return result(request, store.public_collection(store.collection(collection_id)))

    async def prepare(file, material_id=None, revision=1):
        data = await file.read(MAX_BYTES + 1)
        filename = Path((file.filename or "paper.pdf").replace("\\", "/")).name[:180]
        material = {"material_id": material_id or identity(), "revision": revision, "filename": filename,
                    "origin": "upload", "original_filename": filename, "content_source": "upload", "paper_id": None,
                    "byte_size": len(data), "sha256": store.fingerprint(data),
                    "status": "failed", "page_count": 0, "page_checks": [], "warnings": [], "error": None}
        try:
            parsed = await run_in_threadpool(inspect_pdf, data)
            parsed.pop("texts")
            material.update(parsed, status="ready")
        except AppError as exc:
            material["error"] = exc.payload()
        await file.close()
        return material, data if material["status"] == "ready" else b""

    @app.post("/api/v1/collections/{collection_id}/uploads", status_code=202)
    async def upload(request: Request, collection_id: str, expected_revision: int = Form(...), files: list[UploadFile] = File(...)):
        collection = store.editable(collection_id, expected_revision)
        if len(collection["materials"]) + len(files) > 10:
            raise AppError("TOO_MANY_MATERIALS", "最多十篇；本次添加已整批拒绝，原清单保留。", 422)
        prepared = [await prepare(file) for file in files]
        paths = [await run_in_threadpool(store.save_pdf, material["material_id"], data) if data else None for material, data in prepared]
        # Multipart reads can yield: recheck revision before the atomic addition.
        try:
            store.editable(collection_id, expected_revision)
        except AppError:
            for path in paths:
                if path:
                    path.unlink(missing_ok=True)
            raise
        for (material, _), path in zip(prepared, paths):
            collection["materials"].append(material)
            if path:
                store.files[material["material_id"]] = path
        collection["revision"] += 1
        return result(request, store.public_collection(collection))

    @app.put("/api/v1/collections/{collection_id}/materials/{material_id}/file")
    async def replace(request: Request, collection_id: str, material_id: str, expected_revision: int = Form(...), file: UploadFile = File(...)):
        collection, old = store.material(material_id)
        if collection["collection_id"] != collection_id:
            raise AppError("NOT_FOUND", "材料不属于这个清单。", 404)
        store.editable(collection["collection_id"], expected_revision)
        replacement, data = await prepare(file, material_id, old["revision"] + 1)
        replacement.update(origin=old['origin'], paper_id=old['paper_id'])
        path = await run_in_threadpool(store.save_pdf, material_id, data) if data else None
        try:
            store.editable(collection["collection_id"], expected_revision)
        except AppError:
            if path:
                path.unlink(missing_ok=True)
            raise
        collection["materials"][collection["materials"].index(old)] = replacement
        old_path = store.files.pop(material_id, None)
        if path:
            store.files[material_id] = path
        if old_path:
            old_path.unlink(missing_ok=True)
        collection["revision"] += 1
        return result(request, store.public_collection(collection))

    @app.delete("/api/v1/collections/{collection_id}/materials/{material_id}")
    async def remove(request: Request, collection_id: str, material_id: str, expected_revision: int):
        collection, material = store.material(material_id)
        if collection["collection_id"] != collection_id:
            raise AppError("NOT_FOUND", "材料不属于这个清单。", 404)
        store.editable(collection["collection_id"], expected_revision)
        collection["materials"].remove(material)
        path = store.files.pop(material_id, None)
        if path:
            path.unlink(missing_ok=True)
        collection["revision"] += 1
        return result(request, store.public_collection(collection))

    @app.get("/api/v1/materials/{material_id}/pdf")
    async def material_pdf(material_id: str, revision: int):
        _, material = store.material(material_id)
        if material["revision"] != revision or material["status"] != "ready":
            raise AppError("REVISION_CONFLICT", "这个论文版本已经改变或正文不可用。", 409)
        return Response(await run_in_threadpool(store.files[material_id].read_bytes), media_type="application/pdf")

    def find_job(job_id):
        if job_id not in store.jobs:
            raise AppError("NOT_FOUND", "生成任务已过期。", 404)
        return store.jobs[job_id]

    def start(collection, items, language='zh'):
        return enqueue(store, collection, items, **({"generate": generate} if generate else {}),
                       **({"joint_generate": joint_generate} if joint_generate else {}), language=language)

    @app.post("/api/v1/reading-jobs", status_code=202)
    async def reading(request: Request, body: ReadingRequest, idempotency_key: str = Header(...)):
        fingerprint = store.fingerprint(body.model_dump_json().encode())
        if idempotency_key in store.idempotency:
            previous, job_id = store.idempotency[idempotency_key]
            if previous != fingerprint:
                raise AppError("IDEMPOTENCY_CONFLICT", "这个请求标识已用于另一份清单。", 409)
            return result(request, store.public_job(find_job(job_id)))
        collection = store.editable(body.collection_id, body.expected_revision)
        if not collection["materials"] or any(m["status"] != "ready" for m in collection["materials"]):
            raise AppError("MATERIALS_NOT_READY", "请先上传有效正文；所有失败项都需要重新上传或移除。", 409)
        if not (generate if len(collection["materials"]) == 1 else joint_generate) and not settings().api_key:
            raise AppError("MODEL_NOT_CONFIGURED", "请在本机 .env 配置所选模型的 API Key 后再生成。", 409)
        if not (generate if len(collection["materials"]) == 1 else joint_generate):
            ensure_validation_budget()
        job = start(collection, store.snapshot(collection), body.report_language)
        store.idempotency[idempotency_key] = fingerprint, job["job_id"]
        return result(request, store.public_job(job))

    @app.get("/api/v1/jobs/{job_id}")
    async def get_job(request: Request, job_id: str):
        return result(request, store.public_job(find_job(job_id)))

    @app.post("/api/v1/jobs/{job_id}/cancel")
    async def cancel(request: Request, job_id: str):
        job = find_job(job_id)
        if job["status"] in {"queued", "running", "awaiting_decision"}:
            job.update(status="cancelled", phase="已退出生成")
            store.tasks[job_id].cancel()
        return result(request, store.public_job(job))

    @app.post("/api/v1/jobs/{job_id}/retry", status_code=202)
    async def retry(request: Request, job_id: str, idempotency_key: str = Header(...)):
        old = find_job(job_id)
        if old['kind'] == 'language':
            if old['status'] not in {'failed', 'cancelled'}:
                raise AppError('JOB_NOT_RETRYABLE', '只能重试失败或已退出的语言任务。', 409)
            return await report_language_job(request, old['_source_report_id'],
                                             LanguageRequest(report_language=old['language']), idempotency_key)
        fingerprint = "retry:" + job_id
        if idempotency_key in store.idempotency:
            previous, previous_id = store.idempotency[idempotency_key]
            if previous != fingerprint:
                raise AppError("IDEMPOTENCY_CONFLICT", "请求标识已用于其他生成操作。", 409)
            return result(request, store.public_job(find_job(previous_id)))
        if old["status"] not in {"failed", "cancelled"}:
            raise AppError("JOB_NOT_RETRYABLE", "只能重新生成失败或已退出的任务。", 409)
        if old['kind'] == 'overview':
            if not overview_generate and not settings().api_key:
                raise AppError('MODEL_NOT_CONFIGURED', '请先配置本机所选模型的 API Key。', 409)
            if not overview_generate:
                ensure_validation_budget()
            retained = old['_papers'] if old['snapshot'] else None
            job = enqueue_overview(store, source, old['category_codes'], cutoff=date(old['cutoff_at']), retained=retained, language=old['language'],
                                   **({'generate': overview_generate} if overview_generate else {}))
            store.idempotency[idempotency_key] = fingerprint, job['job_id']
            return result(request, store.public_job(job))
        collection = store.editable(old["collection_id"], old["collection_revision"])
        if not (generate if len(old["_items"]) == 1 else joint_generate) and not settings().api_key:
            raise AppError("MODEL_NOT_CONFIGURED", "请在本机 .env 配置密钥后重试。", 409)
        if not (generate if len(old["_items"]) == 1 else joint_generate):
            ensure_validation_budget()
        job = start(collection, [(deepcopy(m), data) for m, data in old["_items"]], old['language'])
        store.idempotency[idempotency_key] = fingerprint, job["job_id"]
        return result(request, store.public_job(job))

    @app.get("/api/v1/reports/{report_id}")
    async def report(request: Request, report_id: str):
        if report_id not in store.reports:
            raise AppError("NOT_FOUND", "报告已过期。", 404)
        return result(request, store.reports[report_id]["report"])

    @app.post('/api/v1/reports/{report_id}/language-jobs', status_code=202)
    async def report_language_job(request: Request, report_id: str, body: LanguageRequest,
                                  idempotency_key: str = Header(...)):
        if body.report_language not in {'zh', 'en', 'bilingual'}:
            raise AppError('INVALID_LANGUAGE', '报告语言不受支持。', 422)
        if report_id not in store.reports:
            raise AppError('NOT_FOUND', '报告已过期。', 404)
        fingerprint = f'language:{report_id}:{body.report_language}'
        if idempotency_key in store.idempotency:
            previous, previous_id = store.idempotency[idempotency_key]
            if previous != fingerprint:
                raise AppError('IDEMPOTENCY_CONFLICT', '请求标识已用于其他语言版本。', 409)
            return result(request, store.public_job(find_job(previous_id)))
        original = store.reports[report_id]['report']
        source_id = original.get('source_report_id') or report_id
        if source_id not in store.reports:
            raise AppError('NOT_FOUND', '原始事实报告已过期。', 404)
        base = store.reports[source_id]['report']
        existing_variant = next((entry['report'] for entry in store.reports.values()
            if entry['report'].get('source_report_id') == source_id and entry['report'].get('language') == body.report_language), None)
        if body.report_language != 'zh' and existing_variant is None:
            if not settings().api_key:
                raise AppError('MODEL_NOT_CONFIGURED', '请先配置本机模型 API Key。', 409)
            ensure_validation_budget()
        job = {'job_id': identity(), 'kind': 'language', 'language': body.report_language,
               'collection_id': None, 'collection_revision': None, 'snapshot': base.get('material_snapshot', []),
               'template_version': base.get('template_version', 2), 'status': 'queued', 'phase': '等待语言转换',
               'completed_pages': 0, 'total_pages': 0, 'report_id': None, 'error': None,
               'usage': {}, 'created_at': now(), 'elapsed_seconds': None, '_source_report_id': source_id}
        store.jobs[job['job_id']] = job
        store.idempotency[idempotency_key] = fingerprint, job['job_id']

        async def run():
            import time
            started = time.monotonic()
            try:
                async with store.ai_lock:
                    job['status'] = 'running'
                    translated = deepcopy(existing_variant) if existing_variant is not None else await translate_report(base, body.report_language, job['usage'],
                                                        lambda label: job.update(phase=label), cache=store.evidence_cache)
                if job['status'] == 'cancelled':
                    return
                new_id = identity()
                translated.update(report_id=new_id, job_id=job['job_id'], source_report_id=source_id)
                store.reports[new_id] = {**store.reports[source_id], 'report': translated}
                job.update(status='succeeded', phase='语言版本已生成', report_id=new_id)
            except asyncio.CancelledError:
                job.update(status='cancelled', phase='已退出语言转换')
            except AppError as exc:
                job.update(status='failed', phase='语言转换失败', error=exc.payload())
            except Exception:
                job.update(status='failed', phase='语言转换失败', error=AppError('INTERNAL_ERROR', '语言转换服务异常。', 500, True).payload())
            finally:
                job['elapsed_seconds'] = round(time.monotonic() - started, 2)

        store.tasks[job['job_id']] = asyncio.create_task(run())
        return result(request, store.public_job(job))

    @app.get("/api/v1/reports/{report_id}/pdf")
    async def report_pdf(report_id: str, material_id: str | None = None):
        if report_id not in store.reports:
            raise AppError("NOT_FOUND", "报告正文已过期。", 404)
        if 'data' not in store.reports[report_id]:
            raise AppError('NOT_FOUND', '速览包含多份独立论文，请从卡片打开对应原文。', 404)
        data = store.reports[report_id]["data"]
        if material_id is None and len(data) == 1:
            material_id = next(iter(data))
        if material_id not in data:
            raise AppError('MATERIAL_ID_REQUIRED', '联合报告请指定需要回看的论文。', 422)
        return Response(data[material_id], media_type="application/pdf")

    dist = ROOT / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
