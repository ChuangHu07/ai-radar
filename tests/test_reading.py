import asyncio
import json
from types import SimpleNamespace as NS
import pytest
from pydantic import ValidationError
from app.errors import AppError
from app.models.contracts import ReportDraft
from app.reading.evidence import read_evidence
from app.reading.provider import document_request, complete_text
from app.reading.quality import KEYS, numbers_in, validate_report
from app.reading.reports import generate_single
from pdf_factory import pdf_bytes


def draft(material_id="m1"):
    return {"title": "明确标注的测试报告", "material_id": material_id,
            "sections": [{"key": key, "narrative": {"zh": "这项实验说明了样本条件。"}, "fact_ids": ["F1"], "evidence_ids": ["E0001"]} for key in KEYS],
            "facts": [{"fact_id": "F1", "statement": "实验使用样本。", "numbers": ["100"], "conditions": "合成测试", "evidence_ids": ["E0001"]}], "warnings": []}


class FakeProvider:
    model = "unit-test-provider"
    def __init__(self, citation_end=2, unreadable=False, count=100):
        self.citation_end, self.unreadable, self.input_count = citation_end, unreadable, count
        self.requests = []
    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass
    async def count(self, system, messages):
        return self.input_count
    async def read(self, system, messages):
        self.requests.append(messages)
        assert messages[0]["content"][0]["citations"]["enabled"]
        return NS(stop_reason="end_turn", content=[NS(type="text", text="[UNREADABLE_PAGE:1]" if self.unreadable else "实验使用 100 个样本。", citations=[NS(type="page_location", document_index=0, start_page_number=1, end_page_number=self.citation_end, cited_text="The experiment used 100 samples.")])], usage=NS(input_tokens=100, output_tokens=20))
    async def format(self, system, messages, schema):
        assert isinstance(messages[0]["content"], str)  # no document/citations in strict JSON request
        assert schema["additionalProperties"] is False
        return NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(draft()))], usage=NS(input_tokens=150, output_tokens=80))


MATERIAL = {"material_id": "m1", "revision": 1, "filename": "synthetic-test.pdf", "page_count": 1, "warnings": []}


def test_two_stage_report_and_usage():
    usage = {}
    report = asyncio.run(generate_single(pdf_bytes(), MATERIAL, usage, lambda *_: None, FakeProvider))
    assert [s["key"] for s in report["sections"]] == KEYS
    assert report["coverage"]["covered_pages"] == [1]
    assert report["evidence"][0]["pdf_page_end_inclusive"] == 1
    assert usage == {"calls": 2, "input_tokens": 250, "output_tokens": 100, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}


def test_completed_evidence_is_reused_only_for_same_revision():
    async def run():
        cache, providers = {}, []
        def factory():
            provider = FakeProvider()
            providers.append(provider)
            return provider
        await generate_single(pdf_bytes(), MATERIAL, {}, lambda *_: None, factory, cache)
        usage = {}
        await generate_single(pdf_bytes(), MATERIAL, usage, lambda *_: None, factory, cache)
        assert len(providers[0].requests) == 1 and not providers[1].requests
        assert usage["calls"] == 1
        await generate_single(pdf_bytes(), {**MATERIAL, "revision": 2}, {}, lambda *_: None, factory, cache)
        assert len(providers[2].requests) == 1
    asyncio.run(run())


@pytest.mark.parametrize("provider,code", [(FakeProvider(citation_end=3), "MODEL_OUTPUT_INVALID"), (FakeProvider(unreadable=True), "SOURCE_COVERAGE_INCOMPLETE"), (FakeProvider(count=80001), "SOURCE_COVERAGE_INCOMPLETE")])
def test_reject_unusable_source(provider, code):
    with pytest.raises(AppError) as error:
        asyncio.run(read_evidence(provider, pdf_bytes(), MATERIAL, {}, lambda *_: None))
    assert error.value.code == code


def test_physical_page_offset_and_recursive_split():
    class CapacityProvider(FakeProvider):
        async def count(self, system, messages):
            import base64
            from app.documents.pdf import inspect_pdf
            content = base64.b64decode(messages[0]["content"][0]["source"]["data"])
            return 80001 if inspect_pdf(content)["page_count"] > 20 else 100
    provider = CapacityProvider()
    pack = asyncio.run(read_evidence(provider, pdf_bytes(pages=41), {**MATERIAL, "page_count": 41}, {}, lambda *_: None))
    assert pack["covered_pages"] == list(range(1, 42))
    assert [e["pdf_page_start"] for e in pack["evidence"]] == [1, 21, 41]


@pytest.mark.parametrize("mutation", ["reference", "sections", "number", "number_prefix", "chinese_number", "material"])
def test_invalid_report_rejected(mutation):
    data = draft()
    if mutation == "reference": data["sections"][0]["evidence_ids"] = ["invented"]
    if mutation == "sections": data["sections"].pop()
    if mutation == "number": data["facts"][0]["numbers"] = ["999"]
    if mutation == "number_prefix": data["facts"][0]["numbers"] = ["10"]
    if mutation == "chinese_number": data["sections"][0]["narrative"]["zh"] = "实验使用999个样本。"
    if mutation == "material": data["material_id"] = "another-paper"
    with pytest.raises(AppError):
        validate_report(ReportDraft.model_validate(data), "m1", [{"evidence_id": "E0001", "source_text": "100 samples"}])


def test_truncation_is_not_success():
    with pytest.raises(AppError):
        complete_text(NS(stop_reason="max_tokens", content=[NS(type="text", text="partial")]))


def test_numeric_tokens_cannot_include_units_or_formulas():
    for number in ("100 samples", "N=6", "10^19"):
        value = draft()
        value["facts"][0]["numbers"] = [number]
        with pytest.raises(ValidationError):
            ReportDraft.model_validate(value)


def test_source_and_draft_available_for_local_quality_review():
    artifacts = {}
    asyncio.run(generate_single(pdf_bytes(), MATERIAL, {}, lambda *_: None, FakeProvider,
                                on_artifact=lambda kind, value: artifacts.update({kind: value})))
    assert artifacts["evidence"]["covered_pages"] == [1]
    assert artifacts["draft"]["facts"][0]["numbers"] == ["100"]


def test_named_metrics_are_not_quantities_and_written_quantities_match():
    assert numbers_in("F1 分数 91.3，8块 P100 GPU，999个样本") == {"91.3", "8", "999"}
    assert numbers_in("36M sentences, 32000 word-piece tokens") == {"36", "32000"}
    assert numbers_in("eight P100 GPUs, twelve hours, twenty-one samples, one hundred and five tests") == {"8", "12", "21", "105"}
    value = draft()
    value["facts"][0].update(statement="实验使用8块 P100 GPU，F1 为91.3。", numbers=["8", "91.3"], conditions="")
    for section in value["sections"]:
        section["narrative"]["zh"] = "使用8块 GPU，F1 为91.3。"
    validate_report(ReportDraft.model_validate(value), "m1", [{"evidence_id":"E0001", "source_text":"eight P100 GPUs; F1 = 91.3"}])
    value["facts"][0]["statement"] = "实验使用9块 GPU。"
    with pytest.raises(AppError):
        validate_report(ReportDraft.model_validate(value), "m1", [{"evidence_id":"E0001", "source_text":"eight P100 GPUs; F1 = 91.3"}])


def test_table_locator_checked_against_cited_page_without_borrowing_quantities():
    value = draft()
    value["facts"][0].update(statement="表2报告100个样本。", numbers=["100"], conditions="")
    source = [{"evidence_id":"E0001", "source_text":"100 samples", "pdf_page_start":1, "pdf_page_end_inclusive":1}]
    validate_report(ReportDraft.model_validate(value), "m1", source, ["Table 2: 100 samples; another study used 999 samples."])
    validate_report(ReportDraft.model_validate(value), "m1", source, ["100 samples", "Table 2: additional comparison"])
    value["facts"][0]["statement"] = "表99报告100个样本。"
    with pytest.raises(AppError):
        validate_report(ReportDraft.model_validate(value), "m1", source, ["Table 2: 100 samples"])
    value["facts"][0]["statement"] = "表2报告999个样本。"
    with pytest.raises(AppError):
        validate_report(ReportDraft.model_validate(value), "m1", source, ["Table 2: 100 samples; another study used 999 samples."])


def test_section_locator_checked_without_changing_measurement_check():
    value = draft()
    value["facts"][0].update(statement="6.1 正文报告100个样本。", numbers=["100"], conditions="")
    source = [{"evidence_id":"E0001", "source_text":"100 samples", "pdf_page_start":1, "pdf_page_end_inclusive":1}]
    validate_report(ReportDraft.model_validate(value), "m1", source, ["6.1 Results\n100 samples"])
    value["facts"][0]["statement"] = "6.9 正文报告100个样本。"
    with pytest.raises(AppError):
        validate_report(ReportDraft.model_validate(value), "m1", source, ["6.1 Results\n100 samples"])
    value["facts"][0]["statement"] = "第22节开发集使用100个样本。"
    validate_report(ReportDraft.model_validate(value), "m1", [{**source[0], "source_text":"Section 22 development set; 100 samples"}])


def test_manual_retry_receives_rejection_and_corrects_citations():
    class CitationProvider(FakeProvider):
        async def read(self, system, messages):
            response = await super().read(system, messages)
            response.content.append(NS(type="text", text="设备条件。", citations=[NS(type="page_location", document_index=0,
                start_page_number=1, end_page_number=2, cited_text="A Vevo 2100 device was used.")]))
            return response

        async def format(self, system, messages, schema):
            payload = json.loads(messages[0]["content"])
            value = draft()
            value["facts"][0]["conditions"] = "使用 Vevo 2100。"
            if "previous_rejection" in payload:
                assert "2100" in payload["previous_rejection"]["validation_error"]
                value["facts"][0]["evidence_ids"].append("E0002")
            return NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(value))], usage=NS(input_tokens=150, output_tokens=80))

    async def run():
        cache, providers = {}, []
        def factory():
            provider = CitationProvider()
            providers.append(provider)
            return provider
        with pytest.raises(AppError, match="2100"):
            await generate_single(pdf_bytes(), MATERIAL, {}, lambda *_: None, factory, cache)
        assert len(providers) == 1  # No automatic paid retry.
        usage = {}
        report = await generate_single(pdf_bytes(), MATERIAL, usage, lambda *_: None, factory, cache)
        assert report["facts"][0]["evidence_ids"] == ["E0001", "E0002"]
        assert not providers[1].requests and usage["calls"] == 1
        assert not any(key[0] == "format_feedback" for key in cache)
        with pytest.raises(AppError, match="2100"):
            await generate_single(pdf_bytes(), {**MATERIAL, "revision": 2}, {}, lambda *_: None, factory, cache)
    asyncio.run(run())
