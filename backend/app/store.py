import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import uuid
import json
import os
from pathlib import Path
import shutil
from .config import settings
from .errors import AppError


def identity():
    return uuid.uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Store:
    """A backend process owns one temporary session; no paper history is persisted."""
    def __init__(self):
        self.session_id = identity()
        self.session_root = settings().data_dir / "sessions"
        self.session_dir = self.session_root / self.session_id
        self.collections = {}
        self.files = {}
        self.jobs = {}
        self.reports = {}
        self.tasks = {}
        self.idempotency = {}
        self.evidence_cache = {}
        self.ai_lock = asyncio.Lock()

    def collection(self, collection_id):
        if collection_id not in self.collections:
            raise AppError("NOT_FOUND", "材料清单已过期，请刷新页面重新上传。", 404)
        return self.collections[collection_id]

    def editable(self, collection_id, revision):
        collection = self.collection(collection_id)
        if collection["revision"] != revision:
            raise AppError("REVISION_CONFLICT", "清单已改变，请刷新后重试。", 409)
        if any(j["collection_id"] == collection_id and j["status"] in {"queued", "running"} for j in self.jobs.values()):
            raise AppError("JOB_ACTIVE", "生成中请先退出，再编辑论文清单。", 409)
        return collection

    def material(self, material_id):
        for collection in self.collections.values():
            for material in collection["materials"]:
                if material["material_id"] == material_id:
                    return collection, material
        raise AppError("NOT_FOUND", "论文已移除或会话已过期。", 404)

    def snapshot(self, collection):
        return [(deepcopy(material), self.files[material["material_id"]].read_bytes())
                for material in collection["materials"]]

    def ensure_session(self):
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "owner.json").write_text(json.dumps({"application": "ai-radar", "pid": os.getpid()}), encoding="utf-8")

    def save_pdf(self, material_id, data):
        self.ensure_session()
        path = self.session_dir / f"{material_id}-{identity()}.pdf"
        path.write_bytes(data)
        return path

    def cleanup_stale_sessions(self):
        if not self.session_root.exists():
            return
        root = self.session_root.resolve()
        for folder in self.session_root.iterdir():
            if folder.is_symlink() or not folder.is_dir() or len(folder.name) != 32:
                continue
            try:
                int(folder.name, 16)
                owner = json.loads((folder / "owner.json").read_text(encoding="utf-8"))
                pid = owner["pid"]
                if owner.get("application") != "ai-radar" or not isinstance(pid, int) or pid <= 0:
                    continue
                dead = False
                if os.name == "nt":
                    # os.kill(pid, 0) is unsafe on Windows; query a handle instead.
                    import ctypes
                    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                    kernel.OpenProcess.restype = ctypes.c_void_p
                    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                    handle = kernel.OpenProcess(0x1000, False, pid)
                    if handle:
                        kernel.CloseHandle(handle)
                    else:
                        dead = ctypes.get_last_error() == 87  # invalid/dead PID; access denied is retained
                else:
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        dead = True
                target = folder.resolve()
                if dead and target.parent == root:
                    shutil.rmtree(target)
            except (OSError, ValueError, KeyError, TypeError):
                continue

    def public_collection(self, collection):
        ready = bool(collection["materials"]) and all(m["status"] == "ready" for m in collection["materials"])
        size = len(collection["materials"])
        related = [j for j in self.jobs.values() if j["collection_id"] == collection["collection_id"] and j["collection_revision"] == collection["revision"]]
        return {**collection, "last_job_id": related[-1]["job_id"] if related else None,
                "material_ids": [m["material_id"] for m in collection["materials"]],
                "derived_mode": "single" if size == 1 else "joint" if size > 1 else None,
                "can_generate": ready and size <= 10,
                "blocking_reasons": (["请上传论文正文。"] if not size else []) +
                [m["error"]["details"] if m.get("error") else f'{m["filename"]} 正文尚未就绪。'
                 for m in collection["materials"] if m["status"] != "ready"]}

    @staticmethod
    def public_job(job):
        return {**{key: value for key, value in job.items() if not key.startswith("_")},
                "progress": {"completed_pages": job["completed_pages"], "total_pages": job["total_pages"]}}

    @staticmethod
    def fingerprint(data):
        return hashlib.sha256(data).hexdigest()

    async def close(self):
        for task in self.tasks.values():
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        self.files.clear()
        self.reports.clear()
        self.evidence_cache.clear()
        # Only this process's UUID directory inside its resolved session root.
        target, root = self.session_dir.resolve(), self.session_root.resolve()
        if target.parent == root and target.name == self.session_id and not self.session_dir.is_symlink():
            shutil.rmtree(target, ignore_errors=True)
