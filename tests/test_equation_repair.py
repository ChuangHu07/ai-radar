import asyncio
import copy
import json
import pytest
from app.errors import AppError
from app.reading.equation_repair import FIELDS, SCHEMA, merge_equation_patch, repair_targets
from app.reading.learning import generate_learning_report, validate_checkpoint, validate_shape
from test_learning import LearningProvider, MATERIAL, review_json
from pdf_factory import pdf_bytes


ORIGINAL = "\n".join(f"<{name}>  原段落 {name} [E0001]\n</{name}>" for name in FIELDS)


def patch(**changes):
    return {"eq_id": "Eq.1", **dict.fromkeys(FIELDS), **changes}


def test_patch_preserves_untouched_bytes_and_schema_stays_closed():
    value = patch(sanity="【教学示例】统一单位后重算 [E0001]")
    validate_shape(value, SCHEMA)
    candidate = merge_equation_patch(ORIGINAL, value, "Eq.1", {"E0001"})
    assert candidate == ORIGINAL.replace("  原段落 sanity [E0001]\n", value["sanity"])
    for invalid in [patch(unknown="extra"), {"eq_id": "Eq.1"}, patch(sanity=123)]:
        with pytest.raises(AppError): validate_shape(invalid, SCHEMA)


@pytest.mark.parametrize("invalid", [
    patch(eq_id="Eq.2", sanity="改错公式"), patch(), patch(sanity=""),
    patch(sanity="无依据 [E9999]"), patch(sanity="<purpose>注入</purpose>"),
    patch(sanity="</sanity>提前结束<sanity>"), patch(sanity=1),
])
def test_patch_rejects_wrong_target_empty_changes_and_untrusted_content(invalid):
    with pytest.raises(AppError): merge_equation_patch(ORIGINAL, invalid, "Eq.1", {"E0001"})


def test_patch_cannot_repair_a_broken_or_duplicate_source_protocol():
    for original in ["plain Markdown", ORIGINAL + "<purpose>重复</purpose>", ORIGINAL + "<sanity>未闭合"]:
        with pytest.raises(AppError): merge_equation_patch(original, patch(sanity="修改"), "Eq.1", {"E0001"})


def test_only_the_explicit_formula_is_targeted():
    equations = [{"eq_id": f"Eq.{i}"} for i in (1, 2, 10)]
    issue = {"problem": "Eq.1 的单位混乱", "fix": "重算 Eq.1。"}
    assert repair_targets(equations, [issue]) == {"Eq.1": [issue]}
    with pytest.raises(AppError): repair_targets(equations, [{"problem": "Eq.9 错", "fix": "核对"}])


class EquationProvider(LearningProvider):
    def __init__(self, bad_patch=False, still_high=False):
        super().__init__()
        self.bad_patch, self.still_high = bad_patch, still_high

    async def format(self, system, messages, schema):
        if "eq_id" in schema["properties"]:
            self.calls.append("D3b-patch")
            assert "previous_tagged_output" in messages[0]["content"]
            assert "<purpose>" in messages[0]["content"]
            assert "输出合约以附带 JSON schema 为准" in system
            self.latest_sanity = "修订计算 [E9999]" if self.bad_patch else f"【教学示例】修订计算第{self.calls.count('D3b-patch')}次 [E0001]"
            return self.response(review_json(patch(sanity=self.latest_sanity)))
        result = await super().format(system, messages, schema)
        value = json.loads(result.content[0].text)
        if "facts" in schema["properties"]:
            value["equations"].append({**value["equations"][0], "eq_id": "Eq.2"})
        if "scores" in schema["properties"] and (self.calls.count("D5") == 1 or self.still_high):
            value.update(overall_pass=False, issues=[{"check": "E5", "section": "equations", "severity": "high",
                "problem": "Eq.1 演算错误", "fix": "重算 Eq.1 直觉检验", "quote": getattr(self, "latest_sanity", "讲解材料 [E0001]")}])
        result.content[0].text = review_json(value)
        return result


def test_structured_repair_retains_report_format_and_unrelated_formula():
    provider = EquationProvider()
    artifacts = {}
    report = asyncio.run(generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None, lambda: provider,
        on_artifact=lambda stage, value: artifacts.update({stage: value})))
    assert report["audit"]["overall_pass"] and len(report["sections"]) == 10
    assert provider.calls.count("D3b") == 2  # The two initial formulas, never a third full rewrite.
    assert provider.calls.count("D3b-patch") == 1 and provider.calls.count("D5") == 2
    assert "修订计算" in artifacts["D3b-Eq.1"]
    assert "修订计算" not in artifacts["D3b-Eq.2"]
    equation_text = next(s for s in report["sections"] if s["key"] == "equations")["narrative"]["zh"]
    assert "### 直觉检验" in equation_text and "<sanity>" not in equation_text


def test_invalid_patch_is_not_cached_or_published_and_retry_reuses_other_work():
    async def run():
        cache = {}
        failed = EquationProvider(bad_patch=True)
        with pytest.raises(AppError, match="不存在的证据"):
            await generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None, lambda: failed, cache)
        assert failed.calls.count("D5") == 1
        assert not any("D3b-patch:Eq.1" in key for key in cache)
        retry = EquationProvider()
        # This fresh review must pass after a patch (its first D5 invocation is now a resumed review).
        original_format = retry.format
        async def passing_review(system, messages, schema):
            response = await original_format(system, messages, schema)
            if "scores" in schema["properties"]:
                value = json.loads(response.content[0].text)
                value.update(overall_pass=True, issues=[])
                response.content[0].text = review_json(value)
            return response
        retry.format = passing_review
        report = await generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None, lambda: retry, cache)
        assert report["resumed_quality_review"] and report["audit"]["overall_pass"]
        assert not {"native", "D1", "D2", "D3a", "D3b", "D3c", "D3d", "D3e"} & set(retry.calls)
        assert retry.calls.count("D3b-patch") == retry.calls.count("D5") == 1
    asyncio.run(run())


def test_still_inaccurate_repairs_remain_blocked_and_checkpoint_is_bound():
    async def run():
        cache = {}
        provider = EquationProvider(still_high=True)
        with pytest.raises(AppError, match="独立审校未通过"):
            await generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None, lambda: provider, cache)
        assert provider.calls.count("D5") == 3 and provider.calls.count("D3b-patch") == 2
        checkpoint = copy.deepcopy(next(v for k, v in cache.items() if "learning-checkpoint" in k))
        facts = next(v for k, v in cache.items() if "D1" in k)
        pack = next(v for k, v in cache.items() if "native-evidence" in k)
        validate_checkpoint(checkpoint, facts, facts["equations"], pack)
        checkpoint["outputs"]["D3b:Eq.1"] += "未审校的新内容"
        with pytest.raises(AppError, match="已审校版本"):
            validate_checkpoint(checkpoint, facts, facts["equations"], pack)
        assert not any("D3b-patch:Eq.1" in key for key in cache)
    asyncio.run(run())
