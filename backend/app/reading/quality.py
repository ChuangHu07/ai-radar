import re
from ..errors import AppError
from ..models.contracts import ReportDraft

KEYS = ["storyline", "prerequisites", "method", "evidence", "limits", "takeaways"]

WORDS = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), range(20)))
WORDS.update(dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10))))
SMALL = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[ -]+(?:one|two|three|four|five|six|seven|eight|nine))?)"
QUANTITY = re.compile(r"\b(?:(?:one|two|three|four|five|six|seven|eight|nine) hundred(?: (?:and )?" + SMALL + r")?|" + SMALL + r")(?: (?:thousand|million))?\b", re.I)
REFERENCE = re.compile(r"(?:(?P<kind>表|图|Table|Figure|Section|小节|章节|节|章)\s*(?P<number>\d+(?:\.\d+)*)|(?P<section_number>\d+(?:\.\d+)+)\s*(?:正文|小节|节|章)|第\s*(?P<reverse_number>\d+(?:\.\d+)*)\s*(?:小节|节|章))", re.I)
SECTION_HEADER = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+[A-Z][A-Za-z]", re.M)
CAPTION_HEADER = re.compile(r"^\s*(Table|Figure)\s+(\d+(?:\.\d+)*)\s*:", re.M | re.I)


def reference_ids(text):
    result = set()
    for match in REFERENCE.finditer(text):
        kind = (match["kind"] or "section").lower()
        result.add(("table" if kind in {"表", "table"} else "figure" if kind in {"图", "figure"} else "section",
                    match["number"] or match["section_number"] or match["reverse_number"]))
    return result


def quantities_in(text):
    return numbers_in(REFERENCE.sub("", text))


def check_references(text, sources, page_texts):
    source_text = " ".join(item["source_text"] for item in sources)
    document_locators = set()
    if page_texts is not None:
        source_text += "\n" + "\n".join(page_texts[page - 1] for item in sources
            for page in range(item["pdf_page_start"], item["pdf_page_end_inclusive"] + 1))
        # A condition may refer readers to another table in the same paper.
        # Only caption/header identities use full-paper text, never measurements.
        for page in page_texts:
            document_locators.update((kind.lower(), number) for kind, number in CAPTION_HEADER.findall(page))
            document_locators.update(("section", number) for number in SECTION_HEADER.findall(page))
    available = reference_ids(source_text) | document_locators | {("section", number) for number in SECTION_HEADER.findall(source_text)}
    if not reference_ids(text) <= available:
        raise AppError("MODEL_OUTPUT_INVALID", "图表或章节编号无法在原始论文的标题中核对。", retryable=True)


def numbers_in(text):
    # PDF typography can encode 'five' as 'ﬁve'. This is an equivalent glyph,
    # not a different quantity; keep signs/digits and scientific symbols intact.
    for glyph, letters in {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}.items():
        text = text.replace(glyph, letters)
    # F1 and P100 are names, while Chinese-adjacent quantities still count.
    values = {value.replace(",", "") for value in re.findall(r"(?<![A-Za-z0-9_])\d[\d,]*(?:\.\d+)?", text)}
    # Native quotations can spell a quantity: 'eight GPUs' supports '8 块 GPU'.
    for phrase in QUANTITY.findall(text):
        value = 0
        for word in phrase.lower().replace("-", " ").split():
            if word in WORDS:
                value += WORDS[word]
            elif word == "hundred":
                value *= 100
            elif word in {"thousand", "million"}:
                value *= 1000 if word == "thousand" else 1000000
        values.add(str(value))
    return values


def validate_report(draft: ReportDraft, material_id: str, evidence: list[dict], page_texts=None) -> ReportDraft:
    if draft.material_id != material_id:
        raise AppError("MODEL_OUTPUT_INVALID", "报告对应的材料与本次选择不同。", retryable=True)
    if len(draft.sections) != 6 or {s.key for s in draft.sections} != set(KEYS):
        raise AppError("MODEL_OUTPUT_INVALID", "报告缺少固定栏目，或存在重复栏目。", retryable=True)
    valid = {e["evidence_id"] for e in evidence}
    fact_ids = {f.fact_id for f in draft.facts}
    if len(fact_ids) != len(draft.facts):
        raise AppError("MODEL_OUTPUT_INVALID", "报告事实标识重复。", retryable=True)
    for fact in draft.facts:
        if not fact.statement.strip() or not fact.evidence_ids or not set(fact.evidence_ids) <= valid:
            raise AppError("MODEL_OUTPUT_INVALID", "事实缺少有效正文来源。", retryable=True)
        sources = [e for e in evidence if e["evidence_id"] in fact.evidence_ids]
        cited = " ".join(e["source_text"] for e in sources)
        check_references(fact.statement + " " + fact.conditions, sources, page_texts)
        for number in quantities_in(fact.statement + " " + fact.conditions):
            if number not in quantities_in(cited):
                raise AppError("MODEL_OUTPUT_INVALID", f"主张 {fact.fact_id[:40]} 中的数字 {number[:60]} 无法在指定引用中核对。", retryable=True)
        for number in fact.numbers:
            if not number.strip() or number.replace(",", "") not in numbers_in(cited):
                raise AppError("MODEL_OUTPUT_INVALID", f"关键数字 {number[:60]} 无法在主张 {fact.fact_id[:40]} 的指定引用中核对。", retryable=True)
    for section in draft.sections:
        if not section.narrative.zh.strip() or not section.evidence_ids or not set(section.evidence_ids) <= valid or not set(section.fact_ids) <= fact_ids:
            raise AppError("MODEL_OUTPUT_INVALID", "栏目内容或来源标识不完整。", retryable=True)
        sources = [e for e in evidence if e["evidence_id"] in section.evidence_ids]
        allowed = " ".join(e["source_text"] for e in sources)
        check_references(section.narrative.zh, sources, page_texts)
        # A number appearing in a section needs to occur in a cited passage.
        for number in quantities_in(section.narrative.zh):
            if number not in quantities_in(allowed):
                raise AppError("MODEL_OUTPUT_INVALID", "讲述中有未对应正文来源的数字。", retryable=True)
    draft.sections.sort(key=lambda s: KEYS.index(s.key))
    return draft
