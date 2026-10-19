"""Read-only model access check. Never prints credentials or request headers."""
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import anthropic
from app.config import settings
from app.reading.provider import model_error


async def main():
    config = settings()
    if not config.api_key:
        print(json.dumps({"status": "not_configured"}))
        return 1
    async with anthropic.AsyncAnthropic(api_key=config.api_key, max_retries=0, timeout=20) as client:
        try:
            page = await client.models.list(limit=100)
            model = await client.models.retrieve(config.model)
            record = {"status": "available", "configured_model": config.model, "model_id": model.id,
                      "display_name": model.display_name, "visible_models": [m.id for m in page.data]}
        except Exception as exc:
            error = model_error(exc)
            record = {"status": "failed", "configured_model": config.model, "error": error.payload(), "exception_type": type(exc).__name__}
        target = ROOT / ".local-data" / "validation"
        target.mkdir(parents=True, exist_ok=True)
        (target / "model-access.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(record, ensure_ascii=True))
        return 0 if record["status"] == "available" else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
