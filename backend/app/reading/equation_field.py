"""Small, isolated formula-field experiment; not a whole-report acceptance gate."""
import json
import re
from . import equation_repair, learning_audit
from ..errors import AppError

VERSION = "equation-single-field-v2"
WRITE_SCHEMA = {"type": "object", "properties": {"markdown": {"type": "string"}},
                "required": ["markdown"], "additionalProperties": False}
CHECKS = ("complete", "formula_consistent", "assumptions_clear", "arithmetic_correct")
REVIEW_SCHEMA = {"type": "object", "properties": {
    **{key: {"type": "boolean"} for key in CHECKS},
    "issues": {"type": "array", "items": {"type": "object", "properties": {
        key: {"type": "string"} for key in ("quote", "severity", "basis", "fix")},
        "required": ["quote", "severity", "basis", "fix"], "additionalProperties": False}}},
    "required": [*CHECKS, "issues"], "additionalProperties": False}


def context(equation, field, evidence, extra_text=""):
    if field not in equation_repair.FIELDS:
        raise AppError("MODEL_OUTPUT_INVALID", "未知公式字段。")
    required = set(equation["evidence_ids"]) | set(re.findall(r"\bE\d{4}\b", extra_text))
    selected = [e for e in evidence if e["evidence_id"] in required]
    if not selected or {e["evidence_id"] for e in selected} != required:
        raise AppError("MODEL_OUTPUT_INVALID", "单字段验证缺少公式原文证据。")
    return {"equation": equation, "field": field, "source_evidence": selected}


def write_request(equation, field, requirements, evidence):
    from .learning import GUARD
    system = "你是论文教学讲解者。本次只写指定字段，输出一个markdown字段的JSON。" + GUARD
    system += "\n写简短但完整的最终说明；一个例子最多5步。不得省略句尾、保留半句话或输出自我纠错过程。"
    data = context(equation, field, evidence, requirements)
    data["field_requirements"] = requirements
    return system, [{"role": "user", "content": json.dumps(data, ensure_ascii=False)}]


def review_request(equation, field, current_markdown, evidence, concepts=()):
    from .learning import GUARD
    system = "你是公式教学审校者。仅审校当前字段及原始公式；没有旧稿或历史审校意见。" + GUARD
    system += """
逐项判断：complete=句子及计算步骤完整；formula_consistent=与给定公式/物理条件一致；
assumptions_clear=教学假设与实测分开；arithmetic_correct=重算正确且单位一致。
不相关的检查可为true。明确事实/数学/条件错误列high或medium，纯措辞建议只列low。
issues只列仍存在的问题，quote逐字摘自current_markdown，basis说明依据或重算步骤，fix给直接修正。
正确内容不因能够写得更长而判失败；不要把已解决的错误或自己的推导写成报告原话。
E开头的ID是原文证据，K开头的ID是concept_index里的概念索引；两者不能混作论文引文。
"""
    data = context(equation, field, evidence, current_markdown)
    data["current_markdown"] = current_markdown
    data["concept_index"] = [{"id": c["id"], "term": c["term"]} for c in concepts]
    return system, [{"role": "user", "content": json.dumps(data, ensure_ascii=False)}]


def checked_field(value, original, eq_id, field, valid_ids):
    from .learning import validate_shape
    validate_shape(value, WRITE_SCHEMA)
    patch = {"eq_id": eq_id, **dict.fromkeys(equation_repair.FIELDS), field: value["markdown"]}
    candidate = equation_repair.merge_equation_patch(original, patch, eq_id, valid_ids)
    return value["markdown"], candidate


def checked_review(value, markdown):
    from .learning import validate_shape
    validate_shape(value, REVIEW_SCHEMA)
    for issue in value["issues"]:
        if (issue["severity"] not in {"high", "medium", "low"}
            or not learning_audit.normalized(issue["quote"])
            or learning_audit.normalized(issue["quote"]) not in learning_audit.normalized(markdown)
            or not issue["basis"].strip() or not issue["fix"].strip()):
            raise AppError("MODEL_AUDIT_UNGROUNDED", "单字段审校缺少当前原句或可核查依据。", 502)
    blocking = any(i["severity"] in {"high", "medium"} for i in value["issues"])
    passed = all(value[key] for key in CHECKS)
    if passed == blocking:
        raise AppError("MODEL_AUDIT_UNGROUNDED", "单字段审校检查结论与问题清单不一致。", 502)
    return passed
