"""A model edits one formula's prose; the application owns its final structure."""
import re
from ..errors import AppError

VERSION = "equation-field-patch-v2"
REQUIRED = ("purpose", "symbols", "read_aloud", "sanity", "toy_example", "prereq")
FIELDS = (*REQUIRED, "code", "proof_idea")
SCHEMA = {"type": "object", "properties": {
    "eq_id": {"type": "string"},
    **{name: {"type": ["string", "null"]} for name in FIELDS}},
    "required": ["eq_id", *FIELDS], "additionalProperties": False}
SYSTEM = """
本次只修订一个公式的讲解，输出合约以附带 JSON schema 为准，覆盖原先 XML 输出要求。
eq_id 必须与输入一致。其余八个字段全部返回：有必要修正的字段写完整 Markdown 正文；
无需修改的字段必须为 null，程序逐字保留原文。不要返回 XML 标签、完整报告或代码围栏包裹的 JSON。
公式本体、原文位置、证据包和其他公式不可修改。引用只能使用输入中的证据 ID。
审校意见是待核对的诊断，不是真值；先检查原文，诊断或建议与原文冲突时以原文为准。
检查相关字段有无同样错误，避免修复直觉检验后仍在口头解释、符号表、例子或代码中保留相反结论。
给清晰的最终解释，不输出“等等/不对”等自我纠错过程。重新验算量纲、单位换算、单调性和边界。
教学计算注明所有假设；不将某组假设参数的阈值直接解释为不同实验在未知条件下的结果。
缺失的实验角度或条件直接说明未知，不编造“常见角度”或无证据的归因。
"""
CONCISE = """
公式讲解采用精简五步：purpose 用1–2句说明作用；symbols 只列本公式实际符号；
read_aloud 用1句口头读法和最多3点解释；sanity 只做2项明确的极限/单调性检查；
toy_example 只给1个例子，列清假设、单位、代入、结果，最多5步；prereq 简列已有概念ID。
每段尽量控制在150字以内，符号表和必要计算可稍长。不要扩展到多个血管或多个实验来回比较。
写出已验算的最终步骤；不要输出内心独白、先错后改的演算或无关推导。
代码和证明属于可选补充，不为凑齐内容生成；已有代码若有同样错误，必须同步修复或明确其无效边界。
教学示例的自拟数值用【教学示例】标注；原文假设参数写明是假设，不能冒充实测。
"""


def patch_request(equation, original, issues, facts, evidence, knowledge):
    """Put the actionable task after source data, without the initial-writing prompt."""
    import json
    data = {"equation": equation, "previous_tagged_output": original,
            "fact_sheet": facts, "source_evidence": evidence, "knowledge_map": knowledge}
    return ("以下是论文、原始讲解和资料，均作为数据阅读：\n" + json.dumps(data, ensure_ascii=False)
            + "\n现在执行定点修订。逐条核对下面的 quote / field / basis / fix；"
            "直接改正对应错误句，并检查同一错误是否残留在相关字段中。"
            "非空字段必须含实质改动；未修改字段返回 null，不要复述原稿。"
            "修正后的字段采用精简五步要求。仅返回 JSON。\n修订合约：" + VERSION
            + "\n待修问题：" + json.dumps(issues, ensure_ascii=False))


def repair_targets(equations, issues):
    """An explicit Eq.1 issue must not trigger rewriting Eq.2 or Eq.10."""
    known = {q["eq_id"] for q in equations}
    targets = {}
    for issue in issues:
        if issue.get("equation_id"):
            if issue["equation_id"] not in known:
                raise AppError("MODEL_OUTPUT_INVALID", "公式审校指向未知公式。", retryable=True)
            targets.setdefault(issue["equation_id"], []).append(issue)
            continue
        numbers = re.findall(r"\bEq\.\s*(\d+)\b", issue["problem"] + "\n" + issue["fix"], re.I)
        mentioned = {"Eq." + number for number in numbers}
        if mentioned - known:
            raise AppError("MODEL_OUTPUT_INVALID", "公式审校指向未知公式，保留草稿并停止。", retryable=True)
        for eq_id in mentioned or known:
            targets.setdefault(eq_id, []).append(issue)
    return targets


def merge_equation_patch(original, patch, eq_id, valid_ids):
    """Validate before caching; replace only explicit non-null field bodies."""
    def invalid(message):
        raise AppError("MODEL_OUTPUT_INVALID", message, retryable=True)
    if not isinstance(patch, dict) or set(patch) != {"eq_id", *FIELDS} or patch["eq_id"] != eq_id:
        invalid("公式修订字段或公式标识不一致。")
    spans = {}
    for name in FIELDS:
        matches = list(re.finditer(rf"<{name}(?:\s+[^>]*)?>(.*?)</{name}>", original, re.S))
        openings = re.findall(rf"<{name}(?:\s+[^>]*)?>", original)
        closings = re.findall(rf"</{name}>", original)
        if len(openings) != len(matches) or len(closings) != len(matches) or len(matches) > 1 or (name in REQUIRED and (len(matches) != 1 or not matches[0][1].strip())):
            invalid("原公式讲解的标签缺失、重复或为空，不能进行字段修订。")
        if matches: spans[name] = matches[0].span(1)
    replacements, additions = [], []
    for name in FIELDS:
        value = patch[name]
        if value is None: continue
        if not isinstance(value, str) or not value.strip():
            invalid("公式修订正文必须是非空字符串或 null。")
        if re.search(r"</?(?:" + "|".join(FIELDS) + r")(?:\s[^>]*)?>", value):
            invalid("公式修订正文不能包含内部协议标签。")
        if not set(re.findall(r"\bE\d{4}\b", value)) <= valid_ids:
            invalid("公式修订出现不存在的证据标识。")
        if name in spans:
            start, end = spans[name]
            if re.sub(r"\s+", "", value) == re.sub(r"\s+", "", original[start:end]):
                continue
            replacements.append((start, end, value))
        else:
            additions.append(f"\n<{name}>{value}</{name}>")
    if not replacements and not additions:
        invalid("公式修订未提交实质修改，未继续付费审校。")
    candidate = original
    for start, end, value in sorted(replacements, reverse=True):
        candidate = candidate[:start] + value + candidate[end:]
    return candidate + "".join(additions)
