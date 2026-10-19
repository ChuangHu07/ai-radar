import json
import asyncio
import pytest
from app.errors import AppError
from app.reading import equation_field as field
from app.reading.equation_repair import FIELDS

EQ = {"eq_id": "Eq.1", "latex": "y=x", "evidence_ids": ["E0001"]}
EVIDENCE = [{"evidence_id": "E0001", "source_text": "y=x"}, {"evidence_id": "E0002", "source_text": "unrelated"}]
ORIGINAL = "".join(f"<{k}>Old {k} [E0001]</{k}>" for k in FIELDS)


def test_probe_only_receives_selected_source_and_current_field():
    _, messages = field.review_request(EQ, "sanity", "Current field.", EVIDENCE)
    data = json.loads(messages[0]["content"])
    assert data["current_markdown"] == "Current field."
    assert data["source_evidence"] == EVIDENCE[:1]
    assert "previous" not in messages[0]["content"]
    with pytest.raises(AppError): field.context(EQ, "unknown", EVIDENCE)
    with pytest.raises(AppError): field.context(EQ, "sanity", [])


def test_single_field_merge_preserves_every_other_byte_and_rejects_extra_fields():
    body, merged = field.checked_field({"markdown": "New sanity [E0001]"}, ORIGINAL, "Eq.1", "sanity", {"E0001"})
    assert merged == ORIGINAL.replace("Old sanity [E0001]", body)
    for value in [{"markdown": "x", "code": "extra"}, {"markdown": "[E9999]"}, {"markdown": ""}, {"markdown": "<purpose>x</purpose>"}]:
        with pytest.raises(AppError): field.checked_field(value, ORIGINAL, "Eq.1", "sanity", {"E0001"})


def test_field_review_receives_every_actual_citation_and_separate_concept_index():
    _, messages = field.review_request(EQ, 'sanity', 'Other claim [E0002], concept K1.', EVIDENCE,
        [{'id': 'K1', 'term': 'sampling'}])
    data = json.loads(messages[0]['content'])
    assert data['source_evidence'] == EVIDENCE
    assert data['concept_index'] == [{'id': 'K1', 'term': 'sampling'}]
    _, messages = field.write_request(EQ, 'sanity', 'Preserve [E0002]', EVIDENCE)
    assert json.loads(messages[0]['content'])['source_evidence'] == EVIDENCE
    with pytest.raises(AppError):
        field.review_request(EQ, 'sanity', 'Unknown [E9999]', EVIDENCE)


def test_review_requires_grounding_and_consistent_decision():
    value = {**dict.fromkeys(field.CHECKS, True), "issues": []}
    assert field.checked_review(value, "result = 2")
    issue = {"quote": "result = 2", "severity": "high", "basis": "1+2=3", "fix": "Use 3"}
    with pytest.raises(AppError): field.checked_review({**value, "issues": [issue]}, "result = 2")
    assert not field.checked_review({**value, "arithmetic_correct": False, "issues": [issue]}, "result = 2")
    with pytest.raises(AppError): field.checked_review({**value, "arithmetic_correct": False, "issues": []}, "result = 2")
    with pytest.raises(AppError): field.checked_review({**value, "issues": [{**issue, "quote": "old draft"}]}, "result = 2")


@pytest.mark.parametrize('reject', [False, True])
def test_pipeline_uses_narrow_generation_and_fresh_review_before_merging(reject):
    from test_equation_repair import EquationProvider
    from test_learning import MATERIAL
    from pdf_factory import pdf_bytes
    from app.reading.learning import generate_learning_report
    class Narrow(EquationProvider):
        supports_field_repair = True
        async def format_field(self, system, messages, schema):
            data = json.loads(messages[0]['content'])
            if 'markdown' in schema['properties']:
                self.calls.append('field-write')
                assert data['field'] == 'sanity' and data['equation']['eq_id'] == 'Eq.1'
                return self.response(json.dumps({'markdown': '已修订的检验 [E0001]'}))
            self.calls.append('field-review')
            assert data['current_markdown'] == '已修订的检验 [E0001]'
            assert 'field_requirements' not in data and 'current_field' not in data
            value = {**dict.fromkeys(field.CHECKS, True), 'issues': []}
            if reject:
                value.update(formula_consistent=False, issues=[{'quote': '已修订的检验', 'severity': 'high', 'basis': '合成不符合公式', 'fix': '重新写检验'}])
            return self.response(json.dumps(value))
    provider = Narrow(); cache = {}; artifacts = {}
    async def run():
        return await generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None, lambda: provider, cache,
            on_artifact=lambda name, value: artifacts.update({name: value}))
    if reject:
        with pytest.raises(AppError, match='当前公式字段未通过'):
            asyncio.run(run())
        assert not any('D3b-field:Eq.1:sanity' in key for key in cache)
        assert provider.calls.count('D5') == 1
        assert '已修订' not in artifacts['D3b-Eq.1']
    else:
        report = asyncio.run(run())
        assert report['audit']['overall_pass'] and provider.calls.count('D5') == 2
        assert '已修订' in artifacts['D3b-Eq.1'] and '已修订' not in artifacts['D3b-Eq.2']
    assert provider.calls.count('field-write') == provider.calls.count('field-review') == 1
    assert 'D3b-patch' not in provider.calls
