import asyncio
from fastapi.testclient import TestClient
from app.main import create_app
from app.errors import AppError
from app.reading.quality import KEYS
from pdf_factory import pdf_bytes


def create(client):
    return client.post("/api/v1/collections", json={}).json()["data"]


def upload(client, collection, data=None):
    return client.post(f'/api/v1/collections/{collection["collection_id"]}/uploads', data={"expected_revision": collection["revision"]}, files={"files": ("paper.pdf", pdf_bytes() if data is None else data, "application/pdf")}).json()["data"]


def start(client, collection, key="test-key"):
    return client.post("/api/v1/reading-jobs", headers={"Idempotency-Key": key}, json={"collection_id": collection["collection_id"], "expected_revision": collection["revision"], "report_language": "zh"})


def test_failed_material_blocked_then_replaced(monkeypatch):
    with TestClient(create_app()) as client:
        collection = upload(client, create(client), b"not-pdf")
        material = collection["materials"][0]
        assert material["status"] == "failed"
        assert start(client, collection).json()["error"]["code"] == "MATERIALS_NOT_READY"
        response = client.put(f'/api/v1/collections/{collection["collection_id"]}/materials/{material["material_id"]}/file', data={"expected_revision": collection["revision"]}, files={"file": ("replacement.pdf", pdf_bytes(), "application/pdf")})
        updated = response.json()["data"]
        assert updated["materials"][0]["material_id"] == material["material_id"]
        assert updated["materials"][0]["revision"] == 2
        assert updated["can_generate"]
        assert client.get(f'/api/v1/materials/{material["material_id"]}/pdf?revision=1').status_code == 409


def test_atomic_limit_and_revision_conflict():
    with TestClient(create_app()) as client:
        collection = create(client)
        url = f'/api/v1/collections/{collection["collection_id"]}/uploads'
        nine = client.post(url, data={"expected_revision": 0}, files=[("files", (f"{i}.pdf", pdf_bytes(), "application/pdf")) for i in range(9)]).json()["data"]
        response = client.post(url, data={"expected_revision": nine["revision"]}, files=[("files", ("x.pdf", pdf_bytes(), "application/pdf")) for _ in range(2)])
        assert response.status_code == 422
        kept = client.get(f'/api/v1/collections/{collection["collection_id"]}').json()["data"]
        assert len(kept["materials"]) == 9 and kept["revision"] == nine["revision"]
        assert client.post(url, data={"expected_revision": 0}, files={"files": ("p.pdf", pdf_bytes())}).status_code == 409


def test_no_key_is_explicit(monkeypatch):
    from app.config import Settings, settings
    config = settings()
    monkeypatch.setattr("app.main.settings", lambda: Settings("", config.model, config.data_dir))
    with TestClient(create_app()) as client:
        assert not client.get("/api/v1/health").json()["data"]["model_configured"]
        assert start(client, upload(client, create(client))).json()["error"]["code"] == "MODEL_NOT_CONFIGURED"


def test_idempotency_cancellation_and_editing():
    async def delayed(data, material, usage, phase):
        await asyncio.sleep(60)
    with TestClient(create_app(generate=delayed)) as client:
        collection = upload(client, create(client))
        response = start(client, collection)
        job = response.json()["data"]
        assert response.status_code == 202
        assert client.get(f'/api/v1/collections/{collection["collection_id"]}').json()["data"]["last_job_id"] == job["job_id"]
        assert start(client, collection).json()["data"]["job_id"] == job["job_id"]
        material = collection["materials"][0]
        url = f'/api/v1/collections/{collection["collection_id"]}/materials/{material["material_id"]}?expected_revision={collection["revision"]}'
        assert client.delete(url).status_code == 409
        assert client.post(f'/api/v1/jobs/{job["job_id"]}/cancel').json()["data"]["status"] == "cancelled"
        assert client.delete(url).json()["data"]["materials"] == []
        assert client.get(f'/api/v1/jobs/{job["job_id"]}').json()["data"]["report_id"] is None


def test_failed_job_retry_keeps_snapshot():
    seen = []
    async def failing(data, material, usage, phase):
        seen.append((data, material["sha256"], material["revision"]))
        raise AppError("SOURCE_COVERAGE_INCOMPLETE", "synthetic-test failure", retryable=True)
    with TestClient(create_app(generate=failing)) as client:
        collection = upload(client, create(client))
        job = start(client, collection).json()["data"]
        failed = client.get(f'/api/v1/jobs/{job["job_id"]}').json()["data"]
        assert failed["status"] == "failed" and failed["report_id"] is None
        retry = client.post(f'/api/v1/jobs/{job["job_id"]}/retry', headers={"Idempotency-Key": "retry-test"}).json()["data"]
        assert retry["job_id"] != job["job_id"]
        assert retry["snapshot"] == job["snapshot"]
        client.get(f'/api/v1/jobs/{retry["job_id"]}')
        assert seen[0] == seen[1]


def test_report_pdf_is_frozen_after_replacement():
    from ui_server import synthetic_report
    original = pdf_bytes(pages=2)
    with TestClient(create_app(generate=synthetic_report)) as client:
        collection = upload(client, create(client), original)
        job = start(client, collection).json()["data"]
        import time
        for _ in range(100):
            completed = client.get(f'/api/v1/jobs/{job["job_id"]}').json()["data"]
            if completed["status"] not in {"queued", "running"}:
                break
            time.sleep(.01)
        assert completed["status"] == "succeeded"
        report_id = completed["report_id"]
        report = client.get(f"/api/v1/reports/{report_id}").json()["data"]
        assert [s["key"] for s in report["sections"]] == KEYS
        material_id = collection["materials"][0]["material_id"]
        client.put(f'/api/v1/collections/{collection["collection_id"]}/materials/{material_id}/file', data={"expected_revision": collection["revision"]}, files={"file": ("new.pdf", pdf_bytes(), "application/pdf")})
        assert client.get(f"/api/v1/reports/{report_id}/pdf").content == original
