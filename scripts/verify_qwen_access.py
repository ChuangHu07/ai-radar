"""One bounded Qwen request. No PDF upload, retries, credential or raw reply logging."""
import asyncio
import json
import os
from pathlib import Path
import sys

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://maas.qianwenaiapi.com/compatible-mode/v1"
MODEL = "qwen3.8-flash"
EXPECTED = {"status": "ok", "language": "zh", "format": "markdown"}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {name: {"type": "string", "enum": [value]} for name, value in EXPECTED.items()},
    "required": list(EXPECTED),
}


def configuration():
    local = dotenv_values(ROOT / ".env")
    def value(name, default=""):
        return str(os.getenv(name) or local.get(name) or default).strip()
    return {"key": value("QWEN_API_KEY"), "model": value("QWEN_MODEL", MODEL),
            "base_url": value("QWEN_BASE_URL", BASE_URL).rstrip("/")}


async def probe(config, transport=None):
    record = {"status": "not_configured", "provider": "qwen", "model": MODEL,
              "calls": 0, "pdf_sent": False}
    if not config.get("key"):
        record["message"] = "请在本机 .env 填写 QWEN_API_KEY。"
        return record
    if config["key"].startswith("sk-sp-"):
        record.update(status="invalid_configuration", message="请使用按量付费密钥，不能使用 Token Plan 密钥。")
        return record
    # This probe is intentionally restricted to the selected official service/model.
    if config.get("base_url") != BASE_URL or config.get("model") != MODEL:
        record.update(status="invalid_configuration", message="检查仅允许已选的千问官方按量接口和 qwen3.8-flash。")
        return record
    body = {
        "model": MODEL, "max_tokens": 128, "enable_thinking": False,
        "messages": [{"role": "user", "content": '只返回 JSON：{"status":"ok","language":"zh","format":"markdown"}。'}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "radar_connection_check", "strict": True, "schema": SCHEMA}},
    }
    try:
        async with httpx.AsyncClient(timeout=60, transport=transport, follow_redirects=False) as client:
            record["calls"] = 1
            reply = await client.post(BASE_URL + "/chat/completions",
                headers={"Authorization": "Bearer " + config["key"]}, json=body)
        record["http_status"] = reply.status_code
        if reply.status_code != 200:
            reason = {401: "密钥未通过认证。", 403: "模型或账户访问被拒绝。",
                      402: "账户余额或计费状态不满足调用条件。", 429: "请求被限流或额度受限。"}
            record.update(status="failed", message=reason.get(reply.status_code, "模型服务返回错误；未自动重试。"))
            return record
        data = reply.json()
        usage = data.get("usage") or {}
        record["usage"] = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                           if isinstance(usage.get(k), int) and not isinstance(usage[k], bool) and usage[k] >= 0}
        choice = data["choices"][0]
        if choice.get("finish_reason") != "stop":
            record.update(status="output_incomplete", message="短请求未完整结束；未自动重试。")
        elif json.loads(choice["message"]["content"]) != EXPECTED:
            record.update(status="output_invalid", message="返回内容不符合连接检查的固定字段；未自动重试。")
        else:
            record.update(status="available", message="连接与简单固定字段输出通过；尚未验证 PDF 或论文报告。")
    except (httpx.TimeoutException, httpx.RequestError):
        record.update(status="connection_failed", message="网络连接失败或超时；未自动重试，是否计费请查看账户账单。")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        record.update(status="output_invalid", message="返回响应无法按固定结构解析；未自动重试。")
    return record


async def main():
    result = await probe(configuration())
    target = ROOT / ".local-data" / "validation" / "qwen-access.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["status"] == "available" else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
