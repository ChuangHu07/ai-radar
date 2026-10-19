"""Official Qwen Chat Completions; explicit native PDF input, bounded calls, no retries."""
import asyncio
import base64
from decimal import Decimal
from io import BytesIO
import json
from math import isfinite
from types import SimpleNamespace as NS

import httpx
from pypdf import PdfReader

from ..config import settings
from ..errors import AppError

BASE_URL = "https://maas.qianwenaiapi.com/compatible-mode/v1"
MODEL = "qwen3.8-flash"
INPUT_RATE = Decimal("0.8") / 1_000_000
OUTPUT_RATE = Decimal("2.7") / 1_000_000
PDF_RATE = Decimal("0.02")


class QwenBudget:
    """Estimated billing guard. Full model context reserved before concurrent requests."""
    def __init__(self, limit=15, max_calls=64):
        if not isfinite(float(limit)) or not 0 < float(limit) <= 15 or not 1 <= max_calls <= 64:
            raise AppError("MODEL_CONFIGURATION_INVALID", "当前千问验证预算必须在 0–15 元内，调用上限 1–64 次。", 409)
        self.limit, self.max_calls = Decimal(str(limit)), max_calls
        self.spent, self.reserved = Decimal(0), Decimal(0)
        self.calls, self.unknown_calls = 0, 0
        self.lock = asyncio.Lock()

    async def reserve(self, output, pages):
        # Native-PDF tokenization is unknown before the reply: use the model's
        # entire 1M context, not a misleading byte/character estimate for billing.
        amount = INPUT_RATE * 1_000_000 + OUTPUT_RATE * (output + 10) + PDF_RATE * pages
        async with self.lock:
            if self.calls >= self.max_calls:
                raise AppError("MODEL_BUDGET_LIMIT", f"本次验证已达到 {self.max_calls} 次调用上限，已停止后续请求；这不表示平台余额或金额预算已用完。", 409)
            if self.spent + self.reserved + amount > self.limit:
                raise AppError("MODEL_BUDGET_LIMIT", "本次千问保守费用预留将超过金额预算，已停止后续请求；这不等于平台余额不足。", 409)
            self.calls += 1
            self.reserved += amount
        return amount

    async def settle(self, reservation, usage):
        async with self.lock:
            self.reserved -= reservation
            if usage is None:
                self.spent += reservation
                self.unknown_calls += 1
                return None
            cost = INPUT_RATE * usage["input_tokens"] + OUTPUT_RATE * usage["output_tokens"] + PDF_RATE * usage["pdf_parsed_pages"]
            self.spent += cost
            return float(cost)


def convert_messages(messages):
    converted, pages = [], 0
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            converted.append({"role": message["role"], "content": content})
            continue
        blocks = []
        for block in content:
            if block["type"] == "text":
                blocks.append({"type": "text", "text": block["text"]})
            elif block["type"] == "document":
                source = block["source"]
                if source.get("type") != "base64" or source.get("media_type") != "application/pdf":
                    raise AppError("MODEL_CONFIGURATION_INVALID", "千问只接受本机冻结的 PDF 原件，不自动下载外部文件。", 409)
                try:
                    data = base64.b64decode(source["data"], validate=True)
                    reader = PdfReader(BytesIO(data))
                    pages += len(reader.pages)
                except Exception as exc:
                    raise AppError("PDF_UNREADABLE", "千问输入的分段 PDF 无法解析。") from exc
                blocks.append({"type": "file", "file": {"filename": "paper.pdf",
                    "file_data": "data:application/pdf;base64," + source["data"]}})
            else:
                raise AppError("MODEL_CONFIGURATION_INVALID", "不支持的千问输入类型；未发送请求。", 409)
        converted.append({"role": message["role"], "content": blocks})
    return converted, pages


def response_usage(raw, expected_pages):
    if not isinstance(raw, dict):
        return None
    def number(value):
        return value if type(value) is int and value >= 0 else None
    inputs, outputs = number(raw.get("prompt_tokens")), number(raw.get("completion_tokens"))
    tool = (raw.get("x_tools") or {}).get("pdf_page_parser") or {}
    parsed = number(tool.get("count")) if expected_pages else 0
    if inputs is None or outputs is None or parsed is None:
        return None
    return {"input_tokens": inputs, "output_tokens": outputs, "pdf_parsed_pages": parsed,
            "cache_read_input_tokens": number((raw.get("prompt_tokens_details") or {}).get("cached_tokens")) or 0}


class QwenProvider:
    supports_field_repair = True
    provider = "qwen"
    count_is_estimate = True
    input_limit = 800_000  # conservative local byte estimate within 1M context

    def __init__(self, config=None, budget=None, transport=None):
        config = config or settings()
        self.model = config.model
        if not config.api_key:
            raise AppError("MODEL_NOT_CONFIGURED", "请在本机 .env 填写 QWEN_API_KEY。", 409)
        if config.api_key.startswith("sk-sp-") or config.base_url.rstrip("/") != BASE_URL or self.model != MODEL:
            raise AppError("MODEL_CONFIGURATION_INVALID", "请使用千问官方按量接口、按量密钥和已验证的 qwen3.8-flash。", 409)
        if not 128 <= config.max_output_tokens <= 32768:
            raise AppError("MODEL_CONFIGURATION_INVALID", "千问输出上限须在 128–32768 Token 内。", 409)
        self.max_output = config.max_output_tokens
        self.key = config.api_key
        self.cache_identity = f"qwen:{BASE_URL}:{self.model}:native-pdf-local-quotes-v2"
        self.budget = budget or QwenBudget(config.budget_cny, config.max_calls)
        self.transport, self.usage_sink = transport, None

    def bind_usage(self, usage):
        self.usage_sink = usage

    async def __aenter__(self):
        # A single HTTP client, no transport retries and no redirect of credentials.
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=20),
                                       transport=self.transport, follow_redirects=False)
        return self

    async def __aexit__(self, *_):
        await self.client.aclose()

    def budget_status(self):
        if self.usage_sink is not None:
            self.usage_sink.update(budget_limit_cny=float(self.budget.limit),
                budget_accounted_cny=float(self.budget.spent), budget_reserved_cny=float(self.budget.reserved),
                unknown_usage_calls=self.budget.unknown_calls, attempted_calls=self.budget.calls)

    async def count(self, system, messages):
        converted, pages = convert_messages(messages)
        text = system + "".join(m["content"] if isinstance(m["content"], str) else
            "".join(b.get("text", "") for b in m["content"]) for m in converted)
        # Local capacity estimate ONLY. Billing uses a separate 1M-context reserve.
        return len(text.encode("utf-8")) + pages * 16384 + 256

    async def read(self, system, messages):
        return await self._complete(system, messages)

    async def format(self, system, messages, schema):
        return await self._complete(system, messages, schema)

    async def read_reasoned(self, system, messages):
        return await self._complete(system, messages, thinking=True)

    async def format_reasoned(self, system, messages, schema):
        return await self._complete(system, messages, schema, thinking=True)

    async def format_field(self, system, messages, schema):
        """A narrow field probe gets a smaller reasoning-plus-answer ceiling."""
        output = 8192 if "issues" in schema.get("properties", {}) else 4096
        return await self._complete(system, messages, schema, max_output=output, thinking=True, thinking_budget=2048)

    async def read_source(self, system, messages, schema):
        return await self._complete(system, messages, schema, max_output=8192)

    async def _complete(self, system, messages, schema=None, max_output=None, thinking=False, thinking_budget=None):
        converted, pages = convert_messages(messages)
        output = min(max_output or self.max_output, self.max_output)
        if schema is not None:
            system += "\n只返回一个完整 JSON 对象，严格遵守合约：\n" + json.dumps(schema, ensure_ascii=False)
        body = {"model": self.model, "messages": [{"role": "system", "content": system}, *converted],
            "max_tokens": output, "enable_thinking": False, "stream": True,
            "stream_options": {"include_usage": True}, "include_tool_usage": True}
        if thinking:
            body.pop("max_tokens")
            # This limit includes reasoning AND the answer. The existing cost
            # reservation therefore still bounds all billable output tokens.
            body.update(enable_thinking=True, thinking_budget=min(thinking_budget or 4096, output // 2), max_completion_tokens=output)
        if schema is not None:
            body["response_format"] = {"type": "json_object"} if pages else {
                "type": "json_schema", "json_schema": {"name": "radar_output", "strict": True, "schema": schema}}
        if len(json.dumps(body).encode()) > 31_000_000:
            raise AppError("SOURCE_COVERAGE_INCOMPLETE", "千问请求体过大，必须拆分页面；未截断或删减材料。", 409)
        reservation = await self.budget.reserve(output, pages)
        self.budget_status()
        text, raw_usage, finish = [], None, None
        settled = False
        try:
            async with self.client.stream("POST", BASE_URL + "/chat/completions",
                    headers={"Authorization": "Bearer " + self.key}, json=body) as response:
                if response.status_code != 200:
                    raise AppError("MODEL_AUTH" if response.status_code in (401, 403) else "MODEL_REQUEST_FAILED",
                        f"千问返回 HTTP {response.status_code}，未自动重试；请检查密钥、额度或模型权限。", 502)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    event = json.loads(payload)
                    if event.get("error"):
                        raise AppError("MODEL_REQUEST_FAILED", "千问流式请求返回错误，未自动重试。", 502)
                    if event.get("usage") is not None:
                        raw_usage = event["usage"]
                    for choice in event.get("choices", []):
                        if choice.get("index", 0) != 0:
                            continue
                        delta = choice.get("delta", {}).get("content")
                        if delta:
                            text.append(delta)
                        if choice.get("finish_reason"):
                            finish = choice["finish_reason"]
            used = response_usage(raw_usage, pages)
            cost = await self.budget.settle(reservation, used)
            settled = True
            self.budget_status()
            if used is None:
                raise AppError("MODEL_USAGE_UNKNOWN", "千问未返回完整用量 / PDF 解析页数，保留费用预留并停止后续调用。", 502)
            # Even rejected / truncated output is returned with usage so the
            # pipeline records its consumption before complete_text rejects it.
            if pages and used["pdf_parsed_pages"] != pages:
                if self.usage_sink is not None:
                    from .provider import add_usage
                    add_usage(self.usage_sink, NS(usage=NS(**used, estimated_cost_cny=cost)))
                raise AppError("SOURCE_COVERAGE_INCOMPLETE", "千问实际 PDF 解析页数与提交页数不一致，未生成全文报告。", 502)
            return NS(stop_reason="end_turn" if finish == "stop" else "max_tokens",
                content=[NS(type="text", text="".join(text), citations=[])],
                usage=NS(**used, estimated_cost_cny=cost))
        except (httpx.RequestError, asyncio.CancelledError) as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise AppError("MODEL_UNAVAILABLE", "千问连接失败或超时；未自动重试，账单可能仍包含已发送请求。", 502, True) from exc
        except (ValueError, TypeError, KeyError) as exc:
            raise AppError("MODEL_OUTPUT_INVALID", "千问流式响应无法解析，未自动重试。", 502, True) from exc
        finally:
            if not settled:
                used = response_usage(raw_usage, pages)
                cost = await self.budget.settle(reservation, used)
                if used is not None and self.usage_sink is not None:
                    from .provider import add_usage
                    add_usage(self.usage_sink, NS(usage=NS(**used, estimated_cost_cny=cost)))
                self.budget_status()
