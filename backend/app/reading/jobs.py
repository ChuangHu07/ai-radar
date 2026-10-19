import asyncio
import time
import json
from ..errors import AppError
from ..store import identity, now
from .learning import generate_learning_report
from .joint import generate_joint_report
from .language import translate_report


def enqueue(store, collection, items, generate=generate_learning_report, joint_generate=generate_joint_report, language='zh'):
    single = len(items) == 1
    job = {"job_id": identity(), "collection_id": collection["collection_id"],
           "kind": "single" if single else "joint", "language": language, "template_version": 2,
           "snapshot": [{"material_id": m["material_id"], "revision": m["revision"], "sha256": m["sha256"]} for m, _ in items],
           "collection_revision": collection["revision"], "status": "queued", "phase": "等待生成",
           "completed_pages": 0, "total_pages": sum(m["page_count"] for m, _ in items), "report_id": None,
           "error": None, "usage": {}, "created_at": now(), "elapsed_seconds": None,
           "_items": items}
    store.jobs[job["job_id"]] = job

    async def run():
        started = time.monotonic()
        try:
            async with store.ai_lock:
                job["status"] = "running"
                def phase(label, completed, total):
                    job.update(phase=label, completed_pages=completed, total_pages=total)
                def artifact(label, value):
                    # Diagnostic content stays inside this process-owned temporary session.
                    (store.session_dir / f'{job["job_id"]}-{label}.json').write_text(
                        json.dumps(value, ensure_ascii=False), encoding="utf-8")
                if single:
                    material, data = items[0]
                    options = {"evidence_cache": store.evidence_cache, "on_artifact": artifact} if generate is generate_learning_report else {}
                    report = await generate(data, material, job["usage"], phase, **options)
                else:
                    options = {"evidence_cache": store.evidence_cache, "on_artifact": artifact} if joint_generate is generate_joint_report else {}
                    report = await joint_generate(items, job["usage"], phase, **options)
                # A cancelled task can never publish a late result.
                if job["status"] == "cancelled":
                    return
                report_id = identity()
                report.update(report_id=report_id, job_id=job["job_id"], created_at=now(),
                              material_snapshot=job["snapshot"], model=report.get("model", "unknown"))
                if single:
                    report.update(material_revision=material["revision"], sha256=material["sha256"], filename=material["filename"])
                store.reports[report_id] = {"report": report, "data": {m["material_id"]: data for m, data in items}}
                if language != 'zh':
                    job['report_id'] = report_id
                    job['phase'] = '转换报告语言'
                    translated = await translate_report(report, language, job['usage'], lambda label: job.update(phase=label), cache=store.evidence_cache)
                    report_id = identity()
                    translated.update(report_id=report_id, job_id=job['job_id'])
                    store.reports[report_id] = {'report': translated, 'data': store.reports[report['report_id']]['data']}
                job.update(status="succeeded", phase="报告已生成", report_id=report_id)
        except asyncio.CancelledError:
            job.update(status="cancelled", phase="已退出生成")
        except AppError as exc:
            job.update(status="failed", phase="生成失败", error=exc.payload())
        except Exception:
            job.update(status="failed", phase="生成失败", error=AppError("INTERNAL_ERROR", "生成服务异常，请重新生成。", 500, True).payload())
        finally:
            job["elapsed_seconds"] = round(time.monotonic() - started, 2)

    store.tasks[job["job_id"]] = asyncio.create_task(run())
    return job
