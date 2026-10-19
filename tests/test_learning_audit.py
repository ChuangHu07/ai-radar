import asyncio
import copy
import json
import math
import pytest
from app.errors import AppError
from app.reading import learning_audit, equation_repair
from app.reading.learning import generate_learning_report, validate_shape, PROMPTS
from test_learning import LearningProvider, MATERIAL, review_json
from pdf_factory import pdf_bytes


def finding(**values):
    return {"check": "E5", "section": "equations", "severity": "high", "problem": "计算错误", "fix": "重新计算",
            "quote": "770 * 10**4 = 770000", "category": "arithmetic", "basis": "按乘法重算",
            "evidence_ids": [], "equation_id": "Eq.1", "field": "toy_example",
            "calculation": {"expression": "770 * 10**4", "reported_value": "770000", "expected_value": "7.7e6", "unit": "教学数值"}, **values}


def grounded(issue):
    quote = "770 * 10**4 = 770000"
    return learning_audit.validate({"issues": [issue]}, {"equations": quote}, {"D3b:Eq.1": f"<toy_example>{quote}</toy_example>"}, [])


def test_perfect_new_review_cannot_forget_an_unchanged_grounded_error():
    review = {"overall_pass": True, "issues": [], "scores": {"E5": 5}}
    issue = finding()
    effective, carried = learning_audit.retain_unresolved(review, [issue], {"equations": issue["quote"]})
    assert not effective["overall_pass"] and carried == [issue]
    assert review["overall_pass"] and review["issues"] == []
    effective, carried = learning_audit.retain_unresolved(review, [issue], {"equations": "770 * 10**4 = 7700000"})
    assert effective["overall_pass"] and not carried  # Do not match a numeric prefix.
    effective, carried = learning_audit.retain_unresolved(review, [issue], {"equations": "结果为 7.7e6"})
    assert effective["overall_pass"] and not carried


def test_downgrading_same_error_does_not_clear_it_or_duplicate_high_findings():
    issue = finding()
    review = {"overall_pass": True, "issues": [{**issue, "severity": "low"}]}
    effective, carried = learning_audit.retain_unresolved(review, [issue], {"equations": issue["quote"]})
    assert not effective["overall_pass"] and carried == [issue]
    again, carried = learning_audit.retain_unresolved(effective, [issue], {"equations": issue["quote"]})
    assert again == effective and not carried


def test_pipeline_blocks_false_pass_when_writer_leaves_known_error_unchanged():
    class ForgetfulReviewer(LearningProvider):
        async def format(self, system, messages, schema):
            if "scores" in schema["properties"]:
                assert "实验主张未支持" not in json.dumps(messages, ensure_ascii=False)
            self.high = "scores" in schema["properties"] and self.calls.count("D5") == 0
            return await super().format(system, messages, schema)
    cache = {}
    provider = ForgetfulReviewer()
    with pytest.raises(AppError, match="独立审校未通过"):
        asyncio.run(generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None, lambda: provider, cache))
    checkpoint = next(v for k, v in cache.items() if "learning-checkpoint" in k)
    assert not checkpoint["audit"]["overall_pass"]
    decision = checkpoint["review_decisions"][-1]
    assert decision["model_review"]["overall_pass"] and not decision["effective_pass"]
    assert decision["carried_findings"]
    assert provider.calls.count("D5") == 3


def test_grounded_arithmetic_is_recalculated_without_executing_code():
    assert grounded(finding())
    assert learning_audit.arithmetic("1540 * 10000 / (4 * 40e6 * cos(radians(85))) * 100") == pytest.approx(110.43449)
    for expr in ['__import__("os")', 'x.y', '(1).__class__', '10**100000', '1/0', 'sqrt(-1)', '[1][0]', 'True', '1e309']:
        with pytest.raises((ValueError, ZeroDivisionError)):
            learning_audit.arithmetic(expr)


def test_correct_calculation_cannot_become_a_blocking_arithmetic_issue():
    issue = finding()
    issue['calculation']['reported_value'] = '7.7e6'
    with pytest.raises(AppError, match="运算成立"):
        grounded(issue)
    issue['calculation']['reported_value'] = '770000'
    issue['calculation']['expected_value'] = '7.7e5'
    with pytest.raises(AppError, match="程序重算不一致"):
        grounded(issue)


def test_verified_arithmetic_error_cannot_be_downgraded_to_a_soft_suggestion():
    with pytest.raises(AppError, match="必须标为 high"):
        grounded(finding(severity="low"))


@pytest.mark.parametrize('changes', [
    {'quote': '报告从未写过的句子'}, {'field': 'sanity'}, {'equation_id': 'Eq.9'},
    {'category': 'source', 'calculation': None, 'evidence_ids': []},
    {'category': 'logic', 'evidence_ids': ['E9999']},
    {'category': 'style', 'calculation': None}, {'basis': ''},
])
def test_review_cannot_invent_its_target_or_basis(changes):
    with pytest.raises(AppError): grounded(finding(**changes))


def test_new_audit_contract_requires_grounding_fields():
    schema = learning_audit.schema(json.loads((PROMPTS / 'D5-schema.json').read_text('utf-8')))
    review = {'overall_pass': False, 'scores': {f'E{i}': 4 for i in range(1,9)}, 'issues': [finding()]}
    validate_shape(review, schema)
    del review['issues'][0]['basis']
    with pytest.raises(AppError): validate_shape(review, schema)


def test_echoed_patch_with_only_whitespace_changes_stops_before_reaudit():
    original = ''.join(f'<{name}>原段落 {name}</{name}>' for name in equation_repair.REQUIRED)
    echoed = {'eq_id': 'Eq.1', **dict.fromkeys(equation_repair.FIELDS), 'sanity': '\n原段落 sanity\n'}
    with pytest.raises(AppError, match='未提交实质修改'):
        equation_repair.merge_equation_patch(original, echoed, 'Eq.1', set())


def test_unfounded_reviewer_is_corrected_before_any_writer_rewrite():
    class Reviewer(LearningProvider):
        async def format(self, system, messages, schema):
            result = await super().format(system, messages, schema)
            if 'scores' in schema['properties']:
                if self.calls.count('D5') == 1:
                    result.content[0].text = review_json({'overall_pass': False, 'scores': {f'E{i}': 4 for i in range(1,9)},
                        'issues': [finding(quote='不存在的错误句')]})
                else:
                    assert '上次审校自身未通过依据检查' in messages[0]['content'][-1]['text']
            return result
    provider = Reviewer()
    report = asyncio.run(generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None, lambda: provider))
    assert report['audit']['overall_pass'] and report['audit_rounds'] == 2
    assert provider.calls.count('D5') == 2 and provider.calls.count('D3a') == provider.calls.count('D3b') == 1


def test_repeated_unfounded_review_remains_blocked_without_silent_downgrade():
    class Reviewer(LearningProvider):
        async def format(self, system, messages, schema):
            result = await super().format(system, messages, schema)
            if 'scores' in schema['properties']:
                result.content[0].text = review_json({'overall_pass': False, 'scores': {f'E{i}': 4 for i in range(1,9)},
                    'issues': [finding(quote='不存在的错误句')]})
            return result
    provider = Reviewer()
    with pytest.raises(AppError, match='错误句不在当前报告'):
        asyncio.run(generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None, lambda: provider))
    assert provider.calls.count('D5') == 2 and provider.calls.count('D3b') == 1


def test_incomplete_review_contract_has_one_bounded_correction():
    class Reviewer(LearningProvider):
        async def format(self, system, messages, schema):
            result = await super().format(system, messages, schema)
            if 'scores' in schema['properties'] and self.calls.count('D5') == 1:
                result.content[0].text = json.dumps({'overall_pass': False, 'scores': {f'E{i}': 4 for i in range(1,9)},
                    'issues': [{'check': 'E5', 'section': 'equations', 'severity': 'high', 'problem': '格式不完整', 'fix': '重新审校'}]})
            return result
    provider = Reviewer()
    report = asyncio.run(generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None, lambda: provider))
    assert report['audit']['overall_pass'] and provider.calls.count('D5') == 2
    assert provider.calls.count('D3b') == 1


def test_legacy_review_is_rechecked_before_following_old_diagnosis():
    async def run():
        cache = {}
        failed = LearningProvider(high=True)
        with pytest.raises(AppError):
            await generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None, lambda: failed, cache)
        checkpoint = next(v for k, v in cache.items() if 'learning-checkpoint' in k)
        checkpoint.pop('audit_contract')
        old_outputs = copy.deepcopy(checkpoint['outputs'])
        retry = LearningProvider()
        report = await generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None, lambda: retry, cache)
        assert report['audit']['overall_pass'] and report['audit_contract'] == learning_audit.VERSION
        assert retry.calls == ['D5']  # No draft rewrite based on the old review.
        assert checkpoint['outputs'] == old_outputs
    asyncio.run(run())

def test_line_selection_preserves_actual_punctuation_and_guards():
    sections = {'knowledge': '概念\n公式“原句”。\n下一句'}
    item = finding(section='knowledge', category='logic', calculation=None,
                   equation_id='', field='', first_line=2, last_line=2, quote='改写的原句')
    audit = learning_audit.materialize({'issues':[item]}, sections)
    assert audit['issues'][0]['quote'] == '公式“原句”。'
    assert item['quote'] == '改写的原句'
    learning_audit.validate(audit, sections, {}, [])
    for first, last in [(0,1), (2,8), (3,2), (True,2)]:
        with pytest.raises(AppError, match='行号'):
            learning_audit.materialize({'issues':[{**item,'first_line':first,'last_line':last}]}, sections)
    audit['issues'][0]['field'] = 'why_needed'
    with pytest.raises(AppError, match='非公式'):
        learning_audit.validate(audit, sections, {}, [])


def test_mapping_blocks_decoded_latex_controls_before_publication():
    from app.reading.learning import validate_map
    with pytest.raises(AppError, match='控制字符'):
        validate_map({'example': 'bad \x08eta and \x0crac'})


def test_pipeline_repairs_one_invalid_mapping_and_retains_failed_draft():
    class InvalidFirstMap(LearningProvider):
        async def format(self, system, messages, schema):
            response = await super().format(system, messages, schema)
            if 'address' in schema['properties'] and self.calls.count('D2') == 1:
                value = json.loads(response.content[0].text)
                value['knowledge_map'][0]['depends_on'] = ['unknown']
                response.content[0].text = json.dumps(value)
            return response
    provider, artifacts = InvalidFirstMap(), {}
    report = asyncio.run(generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_: None,
        lambda: provider, on_artifact=lambda label, value: artifacts.update({label:value})))
    assert report['audit']['overall_pass'] and provider.calls.count('D2') == 2
    assert any(key.startswith('D2-invalid-map-') for key in artifacts)

def test_repair_only_review_keeps_severity_and_requires_grounded_substantive_error():
    logic=finding(section='method',category='logic',calculation=None,equation_id='',field='',quote='错误句')
    style=finding(section='value',category='style',severity='medium',calculation=None,equation_id='',field='',quote='门牌')
    review={'overall_pass':False,'issues':[style,logic]}
    sections={'method':'错误句','value':'门牌'}
    assert learning_audit.validate_candidate(review,sections,{},[])=='repair_only_rejected_review'
    assert review['issues'][0]['severity']=='medium' and not review['overall_pass']
    with pytest.raises(AppError): learning_audit.validate(review,sections,{},[])
    for invalid in [dict(review,overall_pass=True),dict(review,issues=[style]),
                    dict(review,issues=[style,{**logic,'quote':'不存在的句子'}]),
                    dict(review,issues=[style,{**logic,'evidence_ids':['E9999']}])]:
        with pytest.raises(AppError): learning_audit.validate_candidate(invalid,sections,{},[])


def test_mixed_invalid_style_review_drives_repair_but_only_fresh_strict_review_publishes():
    class MixedReviewer(LearningProvider):
        async def format(self,system,messages,schema):
            self.high='scores' in schema['properties'] and self.calls.count('D5')==0
            response=await super().format(system,messages,schema)
            if 'scores' in schema['properties'] and self.calls.count('D5')==1:
                value=json.loads(response.content[0].text)
                value['issues'].append(finding(section='value',category='style',severity='medium',
                    calculation=None,equation_id='',field='',quote='讲解材料 [E0001]',problem='措辞需调整'))
                response.content[0].text=json.dumps(value)
            return response
        async def read(self,system,messages):
            response=await super().read(system,messages)
            if self.calls.count('D5')>=1 and ('实验怎么读' in system or '这篇论文有什么用' in system):
                response.content[0].text=response.content[0].text.replace('讲解材料','核对后材料')
            return response
    provider=MixedReviewer()
    report=asyncio.run(generate_learning_report(pdf_bytes(),MATERIAL,{},lambda *_:None,lambda:provider))
    assert report['audit']['overall_pass'] and provider.calls.count('D5')==2
    first=report['review_decisions'][0]
    assert first['purpose']=='repair_only_rejected_review' and not first['effective_pass']
    assert first['model_review']['issues'][-1]['severity']=='medium'
    assert report['review_decisions'][-1]['purpose']=='strict_review'
