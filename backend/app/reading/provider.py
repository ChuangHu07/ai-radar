import base64
import json
from pathlib import Path
import anthropic
from ..config import settings
from ..errors import AppError


def model_error(exc: Exception) -> AppError:
    if isinstance(exc, anthropic.AuthenticationError):
        return AppError("MODEL_AUTH", "API 密钥无效，请检查本机 .env。", 502)
    if isinstance(exc, anthropic.RateLimitError):
        return AppError("MODEL_RATE_LIMIT", "Claude 请求被限流，请稍后重新生成。", 502, True)
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return AppError("MODEL_UNAVAILABLE", "无法连接 Claude，或模型请求超时。", 502, True)
    if isinstance(exc, anthropic.APIStatusError):
        body = getattr(exc, "body", {}) or {}
        raw = body.get("error", body) if isinstance(body, dict) else {}
        detail = raw.get("message", "模型服务返回错误。") if isinstance(raw, dict) else "模型服务返回错误。"
        key = settings().api_key
        detail = str(detail).replace(key, "[redacted]") if key else str(detail)
        code = "MODEL_CREDIT" if "credit" in detail.lower() else "MODEL_REQUEST_FAILED"
        return AppError(code, f"Claude 返回 HTTP {exc.status_code}：{detail[:260]}", 502, True)
    return AppError("MODEL_OUTPUT_INVALID", "模型返回内容无法解析或核查。", 502, True)


class ClaudeProvider:
    def __init__(self):
        config = settings()
        if config.provider != "claude":
            raise AppError("MODEL_CONFIGURATION_INVALID", "当前选择千问，不能直接调用 Claude 或自动回退。", 409)
        if not config.api_key:
            raise AppError("MODEL_NOT_CONFIGURED", "请先在本机 .env 填写 ANTHROPIC_API_KEY，再生成报告。", 409)
        self.model = config.model
        self.provider = "claude"
        self.cache_identity = f"claude:https://api.anthropic.com:{self.model}:native-citations-v1"
        self.client = anthropic.AsyncAnthropic(api_key=config.api_key, max_retries=0, timeout=180)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.client.close()

    async def count(self, system: str, messages: list) -> int:
        response = await self.client.messages.count_tokens(model=self.model, system=system, messages=messages)
        return response.input_tokens

    async def read(self, system: str, messages: list):
        return await self._complete(system, messages)

    async def _complete(self, system, messages, schema=None):
        options = {} if schema is None else {"output_config":{"format":{"type":"json_schema", "schema":schema}}}
        # Receive long reports incrementally; publish only the complete final
        # message. The read timeout now measures idle time, not the whole draft.
        async with self.client.messages.stream(model=self.model, max_tokens=32768,
                system=system, messages=messages, **options) as stream:
            return await stream.get_final_message()

    async def format(self, system: str, messages: list, schema: dict):
        # Learning schemas exceed the provider grammar compiler's complexity
        # budget. Keep their exact JSON contracts and validate locally, without
        # issuing a rejected structured request followed by another paid call.
        if any(key in schema.get("properties", {}) for key in ("key_equations", "knowledge_map", "scores")):
            return await self._complete(system + "\n只返回一个完整 JSON 对象，不使用代码围栏；严格遵守给定字段和类型。", messages)
        return await self._complete(system, messages, schema)


def ModelProvider():
    """An explicit selection, never a paid fallback to another provider."""
    if settings().provider == "qwen":
        from .qwen import QwenProvider
        return QwenProvider()
    return ClaudeProvider()


def cache_model(provider):
    return getattr(provider, "cache_identity", getattr(provider, "model", type(provider).__name__))


def document_request(data: bytes, title: str, prompt: str) -> list:
    return [{"role": "user", "content": [
        {"type": "document", "title": title, "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(data).decode("ascii")}, "citations": {"enabled": True}},
        {"type": "text", "text": prompt}]}]


def complete_text(message) -> str:
    if message.stop_reason != "end_turn":
        raise AppError("MODEL_OUTPUT_INCOMPLETE", "模型输出被截断、拒绝或未完整结束，请重新生成。", retryable=True)
    return "\n".join(b.text for b in message.content if b.type == "text")


def add_usage(total: dict, message):
    for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
                "pdf_parsed_pages", "estimated_cost_cny"):
        if key in {"pdf_parsed_pages", "estimated_cost_cny"} and not hasattr(message.usage, key):
            continue
        total[key] = total.get(key, 0) + (getattr(message.usage, key, 0) or 0)
    total["calls"] = total.get("calls", 0) + 1
