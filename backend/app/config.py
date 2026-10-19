from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    data_dir: Path
    provider: str = "claude"
    base_url: str = ""
    budget_cny: float = 15.0
    max_calls: int = 64
    max_output_tokens: int = 16384


def settings() -> Settings:
    # Read on demand so editing the local .env does not require a restart.
    local = dotenv_values(ROOT / ".env")
    def value(name: str, default: str = "") -> str:
        return os.getenv(name) or local.get(name) or default
    data = Path(value("AI_RADAR_DATA_DIR", ".local-data"))
    provider = value("AI_RADAR_PROVIDER", "claude").strip().lower()
    if provider not in {"claude", "qwen"}:
        from .errors import AppError
        raise AppError("MODEL_CONFIGURATION_INVALID", "AI_RADAR_PROVIDER 必须是 claude 或 qwen。", 409)
    qwen = provider == "qwen"
    try:
        budget = float(value("AI_RADAR_BUDGET_CNY", "15"))
        calls = int(value("AI_RADAR_MAX_CALLS", "64"))
        output = int(value("AI_RADAR_MAX_OUTPUT_TOKENS", "16384"))
    except ValueError as exc:
        from .errors import AppError
        raise AppError("MODEL_CONFIGURATION_INVALID", "预算、调用次数和输出上限必须是有效数字。", 409) from exc
    return Settings(value("QWEN_API_KEY" if qwen else "ANTHROPIC_API_KEY"),
                    value("QWEN_MODEL", "qwen3.8-flash") if qwen else value("CLAUDE_MODEL", "claude-sonnet-5-5"),
                    (data if data.is_absolute() else ROOT / data).resolve(), provider,
                    value("QWEN_BASE_URL", "https://maas.qianwenaiapi.com/compatible-mode/v1") if qwen else "https://api.anthropic.com",
                    budget, calls, output)
