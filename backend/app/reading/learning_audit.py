"""Ground review findings in the actual draft, sources and checkable arithmetic."""
import ast
import copy
import math
import re
from ..errors import AppError
from .equation_repair import FIELDS

VERSION = "grounded-learning-audit-v2"
GUIDANCE = """
审校合约 grounded-learning-audit-v2：先核对，再提出问题；不要为了找问题而找问题。scores 严格取1–5。
每条 issue 必须提供 quote（逐字摘取当前报告的具体错误句，不带省略号）、category、basis、
evidence_ids、equation_id 和 field。非公式问题后二项用空串；公式问题必须给实际公式ID和正文标签名。
category 仅为 source/arithmetic/logic/coverage/style。basis 写清原文或逻辑依据，fix 给直接可执行的修正。
source 问题须给实际相关 evidence_ids，完整阅读该引用，不能忽略引用前半段然后断言“未提及”。
arithmetic 问题须在 calculation 填 expression / reported_value / expected_value / unit；其他类别填 null。
expression 使用普通数字算式 + - * / **、pi、sin/cos/sqrt/radians/abs，可用科学计数法。
reported_value 是报告声称的该算式值；expected_value 是独立重算值。运算相等不得判算术错误。
必须区分公式条件/数学错误与显示建议。正确的科学计数法、已有的计算步骤、较长措辞不属于事实错误。
不误导读者的排版/措辞建议仅标 style/low；明确事实/公式/算术错误仍须 high，条件遗漏视影响为 medium/high。
检查一个公式的所有字段，避免 sanity 修好后 read_aloud 仍说相反结论；每个受影响字段单独列问题。
反查自己的诊断：原稿是否已经说清你要求添加的步骤？你的修订建议是否只是重述原稿？若是，取消该条。
检查教学计算中的单位、投影、往返路径/倍数、假设与实测边界；“量级接近”不能掩盖已知的倍数错误。
保留所有固定栏目和五步教学要求；简洁但准确的解释可通过，无需为了比喻、代码或长推导增加篇幅。
每条 issue 还须提供 first_line / last_line，使用 assembled_lines 中该 section 的连续行号定位错误。
程序会从实际报告提取 quote；不得选择空行、其他部分或改写报告原句。公式错误若位于 knowledge 等非 equations 部分，equation_id 和 field 仍必须为空串。
"""


def schema(base):
    value = copy.deepcopy(base)
    issue = value["properties"]["issues"]["items"]
    fields = {k: {"type": "string"} for k in ("quote", "category", "basis", "equation_id", "field")}
    fields["evidence_ids"] = {"type": "array", "items": {"type": "string"}}
    fields.update({key: {"type": "integer", "minimum": 1} for key in ("first_line", "last_line")})
    fields["calculation"] = {"type": ["object", "null"], "properties": {
        k: {"type": "string"} for k in ("expression", "reported_value", "expected_value", "unit")},
        "required": ["expression", "reported_value", "expected_value", "unit"], "additionalProperties": False}
    issue["properties"].update(fields)
    issue["required"].extend(key for key in fields if key not in {"first_line", "last_line"})
    return value


def numbered_sections(sections):
    return {key: [{"line": i + 1, "text": line} for i, line in enumerate(text.splitlines(keepends=True))]
            for key, text in sections.items()}


def materialize(audit, sections):
    """Locate findings in immutable draft lines, then retain all existing guards."""
    result = copy.deepcopy(audit)
    for issue in result["issues"]:
        # Legacy saved reviews remain subject to their original exact-quote check.
        if "first_line" not in issue and "last_line" not in issue:
            continue
        lines = sections.get(issue["section"], "").splitlines(keepends=True)
        first, last = issue.get("first_line"), issue.get("last_line")
        if type(first) is not int or type(last) is not int or not 1 <= first <= last <= len(lines):
            raise AppError("MODEL_AUDIT_UNGROUNDED", "审校行号不在当前报告范围内。", 502, True)
        quote = "".join(lines[first - 1:last]).strip()
        if not quote:
            raise AppError("MODEL_AUDIT_UNGROUNDED", "审校不能选择空行。", 502, True)
        issue["quote"] = quote
    return result


def arithmetic(expression):
    """Tiny numerical grammar; no eval, attributes, indexing, imports or unbounded powers."""
    if not isinstance(expression, str) or len(expression) > 240:
        raise ValueError("算式过长")
    tree = ast.parse(expression, mode="eval")
    if len(list(ast.walk(tree))) > 80: raise ValueError("算式过长")
    functions = {"sin": math.sin, "cos": math.cos, "sqrt": math.sqrt, "radians": math.radians, "abs": abs}
    def number(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float): value = float(node.value)
        elif isinstance(node, ast.Name) and node.id == "pi": value = math.pi
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = number(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp):
            left, right = number(node.left), number(node.right)
            if isinstance(node.op, ast.Add): value = left + right
            elif isinstance(node.op, ast.Sub): value = left - right
            elif isinstance(node.op, ast.Mult): value = left * right
            elif isinstance(node.op, ast.Div): value = left / right
            elif isinstance(node.op, ast.Pow) and abs(right) <= 12: value = left ** right
            else: raise ValueError("不支持的运算")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions and len(node.args) == 1 and not node.keywords:
            value = functions[node.func.id](number(node.args[0]))
        else: raise ValueError("不支持的算式")
        if isinstance(value, complex) or not math.isfinite(value) or abs(value) > 1e100:
            raise ValueError("无效计算结果")
        return value
    return number(tree.body)


def normalized(text):
    return re.sub(r"\s+", "", text).replace("\\\\", "\\")


def retain_unresolved(review, previous, sections, outputs=None):
    """A reviewer omission cannot clear a previously grounded, unchanged error.

    Returns a separate effective decision; callers retain the raw model review.
    A changed quote still needs a fresh review, not an automatic correctness claim.
    """
    result = copy.deepcopy(review)
    carried = []
    for issue in previous:
        quote = normalized(issue.get("quote", ""))
        if issue["severity"] not in {"medium", "high"} or not quote:
            continue
        target = sections.get(issue["section"], "")
        if issue["section"] == "equations" and outputs is not None:
            text = outputs.get("D3b:" + issue.get("equation_id", ""), "")
            field = issue.get("field", "")
            match = re.search(rf"<{re.escape(field)}(?:\s+[^>]*)?>(.*?)</{re.escape(field)}>", text, re.S)
            target = match[1] if match else ""
        target = normalized(target)
        matches = list(re.finditer(re.escape(quote), target))
        if not any(not (quote[-1].isdigit() and m.end() < len(target) and target[m.end()] in "0123456789.") for m in matches):
            continue
        if not any(normalized(i.get("quote", "")) == quote and i["severity"] in {"medium", "high"}
                   for i in result["issues"]):
            result["issues"].append(copy.deepcopy(issue))
            carried.append(copy.deepcopy(issue))
    if carried:
        result["overall_pass"] = False
    return result, carried


def validate(audit, sections, outputs, evidence):
    valid_ids = {e["evidence_id"] for e in evidence}
    def invalid(message):
        raise AppError("MODEL_AUDIT_UNGROUNDED", message, 502, True)
    for issue in audit["issues"]:
        section = issue["section"]
        if section not in sections: invalid("审校指向不存在的报告部分。")
        category = issue["category"]
        if category not in {"source", "arithmetic", "logic", "coverage", "style"}:
            invalid("审校问题类别无效。")
        if not issue["basis"].strip() or not issue["fix"].strip(): invalid("审校缺少核查依据或可执行修改。")
        quote = normalized(issue["quote"])
        if not quote or quote not in normalized(sections[section]):
            invalid("审校所指的错误句不在当前报告中，须重新核对 quote。")
        if not set(issue["evidence_ids"]) <= valid_ids: invalid("审校引用了不存在的原文证据。")
        if category == "source" and not issue["evidence_ids"]: invalid("原文一致性问题缺少可回看的证据。")
        if category == "style" and issue["severity"] != "low": invalid("轻微表达建议不能作为阻断问题。")
        if section == "equations":
            text = outputs.get("D3b:" + issue["equation_id"])
            field = issue["field"]
            if text is None or field not in FIELDS: invalid("公式审校缺少实际公式编号或字段。")
            match = re.search(rf"<{field}(?:\s+[^>]*)?>(.*?)</{field}>", text, re.S)
            if not match or quote not in normalized(match[1]): invalid("错误句与公式字段不对应。")
        elif issue["equation_id"] or issue["field"]:
            invalid("非公式问题不能指定公式字段。")
        calculation = issue["calculation"]
        if category == "arithmetic":
            if calculation is None: invalid("算术问题缺少可重算步骤。")
            try:
                actual = arithmetic(calculation["expression"])
                reported = arithmetic(calculation["reported_value"])
                expected = arithmetic(calculation["expected_value"])
            except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, TypeError):
                invalid("审校给出的算式无法安全重算。")
            if not math.isclose(actual, expected, rel_tol=0.001, abs_tol=1e-10):
                invalid("审校给出的正确值与程序重算不一致。")
            if math.isclose(actual, reported, rel_tol=0.001, abs_tol=1e-10):
                invalid("报告中的该运算成立，不能作为算术错误阻断；请检查是否仅为表达建议。")
            if issue["severity"] != "high":
                invalid("已核实的算术错误必须标为 high，不能作为轻微建议放行。")
        elif calculation is not None:
            invalid("非算术问题的 calculation 必须为 null。")
    return audit


def validate_candidate(audit, sections, outputs, evidence):
    """Accept grounded rejected findings for repair, never as a release verdict.

    A mixed review with a misclassified style severity must not prevent repair
    of real source/logic errors. Only the validation view changes; the original
    rejection and every severity are retained. Publication still uses validate.
    """
    try:
        validate(audit, sections, outputs, evidence)
        return 'strict_review'
    except AppError as original:
        if audit.get('overall_pass') is not False or not any(
            i['category'] != 'style' and i['severity'] in {'medium', 'high'} for i in audit['issues']):
            raise
        view = copy.deepcopy(audit)
        misclassified = False
        for issue in view['issues']:
            if issue['category'] == 'style' and issue['severity'] in {'medium', 'high'}:
                issue['severity'] = 'low'
                misclassified = True
        if not misclassified: raise
        # Check every quote, source, equation field and calculation, including
        # issues after the style problem which caused the first validation exit.
        validate(view, sections, outputs, evidence)
        return 'repair_only_rejected_review'
