import asyncio
import json
from types import SimpleNamespace as NS
import pytest
from app.errors import AppError
from app.reading.learning import (generate_learning_report, validate_audit, validate_map,
                                  validate_tags, validate_shape, rule_check, VERSION)
from pdf_factory import pdf_bytes


def review_json(value, **kwargs):
    # Synthetic reviews still obey the same grounding contract as production.
    if isinstance(value, dict) and 'scores' in value:
        for issue in value['issues']:
            issue.setdefault('quote', '从总体选择部分观测。' if issue['section'] == 'knowledge' else '讲解材料 [E0001]')
            issue.setdefault('category', 'style' if issue['severity'] == 'low' else 'logic')
            issue.setdefault('basis', '合成用例：核查指定讲解与所设测试条件。')
            issue.setdefault('evidence_ids', ['E0001'])
            issue.setdefault('equation_id', 'Eq.1' if issue['section'] == 'equations' else '')
            issue.setdefault('field', 'sanity' if issue['section'] == 'equations' else '')
            issue.setdefault('calculation', None)
    return json.dumps(value, **kwargs)


def mapping():
    return {"address": {key: {"name": key, "tension": "背景中的问题 [E0001]"} if key != "street" else
        {"name": "具体贡献", "contribution": "样本测量 [E0001]", "headline_result": "100 samples [E0001]"}
        for key in ["earth", "country", "state", "city", "street"]}, "neighbors": [], "vacancy": "原文未说明 [E0001]",
        "work_type": {"primary": "勘探", "secondary": None},
        "knowledge_map": [{"id":"K1", "level":"L1", "term":"采样", "en":"sampling", "why_needed":"理解实验", "enough_standard":"区分样本与总体即可",
                           "self_check":{"q":"样本代表全部总体吗？", "a":"不能自动推广。"}, "quick_explain":"从总体选择部分观测。", "learn_from":[], "depends_on":[]}],
        "routes": {level: {"prerequisites_in_order":["K1"], "focus":["核心思想"], "skip":[], "estimated_time":"教学估计", "paper_reading_order":"物理第1页"}
                   for level in ["beginner","intermediate","expert"]}}


class LearningProvider:
    model = "synthetic-learning-test"
    def __init__(self, high=False, equation=True, fail_writing=False):
        self.calls, self.high, self.equation, self.fail_writing = [], high, equation, fail_writing
    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass
    async def count(self, *_): return 200
    def response(self, text):
        return NS(stop_reason="end_turn", content=[NS(type="text", text=text)], usage=NS(input_tokens=100, output_tokens=50))
    async def read(self, system, messages):
        if isinstance(messages[0]["content"], list):
            self.calls.append("native")
            r = self.response("事实样本")
            r.content[0].citations = [NS(type="page_location", document_index=0, start_page_number=1, end_page_number=2, cited_text="The experiment used 100 samples.")]
            return r
        for phrase, stage, tags in [
            ("两个核心部分", "D3a", ["core_idea","method"]), ("为一个公式写精讲", "D3b", ["purpose","symbols","read_aloud","sanity","toy_example","prereq"]),
            ("实验怎么读", "D3c", ["claims_evidence","how_to_read","strongest","weakest","reproduce"]),
            ("这篇论文有什么用", "D3d", ["academic","engineering","limitations","takeaway"]),
            ("最后部分", "D3e", ["quiz","feynman","next_reading"]), ("页面顶部的导读", "D4", ["quick_card","routes","glossary","consistency_fixes"])]:
            if phrase in system:
                self.calls.append(stage)
                if self.fail_writing and stage == "D3c": raise AppError("MODEL_UNAVAILABLE", "synthetic connection failure", retryable=True)
                return self.response("\n".join(f"<{name}>讲解材料 [E0001]</{name}>" for name in tags))
        raise AssertionError("Unexpected writing stage")
    async def format(self, system, messages, schema):
        props = schema["properties"]
        if "facts" in props:
            self.calls.append("D1")
            value = {"title":"合成学习报告", "material_id":"m1", "facts":[{"fact_id":"F1","statement":"实验使用100个样本。","numbers":["100"],"conditions":"合成测试","evidence_ids":["E0001"]}],
                     "equations":[{"eq_id":"Eq.1","latex":"y=x", "where":"物理第1页 [E0001]","evidence_ids":["E0001"], "transcription_status":"PDF 转写"}] if self.equation else [],
                     "method":{"overview":"", "components":[]}, "key_equations":[], "experiments":{"ablations":[], "cost":None},
                     "contributions":[], "prior_work":[], "resources":{}, "limitations_by_authors":[], "concepts":[], "figures":[], "one_line_by_authors":"", "extraction_notes":"合成测试"}
        elif "address" in props:
            self.calls.append("D2")
            value = mapping()
        else:
            self.calls.append("D5")
            documents = messages[0]["content"]
            if self.equation:
                assert isinstance(documents,list) and documents[0]["type"] == "document"
                assert not documents[0]["citations"]["enabled"]
            value = {"overall_pass":not self.high,"scores":{f"E{i}":4 for i in range(1,9)},"issues":[{"check":"E1","section":"experiments","severity":"high","problem":"实验主张未支持","fix":"删除不支持的主张"}] if self.high else []}
        def fill(s, item=None):
            kind = s["type"]
            if kind == "object": return {k:fill(v, (item or {}).get(k)) for k,v in s["properties"].items()
                                         if k in s.get("required", s["properties"]) or k in (item or {})}
            if kind == "array": return [fill(s["items"],x) for x in (item or [])]
            if item is not None: return item
            return None if isinstance(kind,list) else {"string":"", "boolean":False,"integer":0}[kind]
        return self.response(review_json(fill(schema,json.loads(review_json(value)))))


MATERIAL = {"material_id":"m1", "revision":1, "sha256":"synthetic", "page_count":1, "filename":"test.pdf", "warnings":[]}


def test_learning_pipeline_uses_pdf_audit_and_ten_sections():
    provider = LearningProvider()
    report = asyncio.run(generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_:None, lambda:provider))
    assert report["template_version"] == 2 and report["prompt_version"] == VERSION
    assert len(report["sections"]) == 10 and report["audit"]["overall_pass"]
    assert provider.calls.count("native") == 1 and provider.calls.count("D5") == 1
    assert "PDF 公式转写" in next(s for s in report["sections"] if s["key"]=="equations")["narrative"]["zh"]


def test_no_equation_hides_section_and_high_issues_never_publish():
    provider = LearningProvider(equation=False)
    report = asyncio.run(generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_:None, lambda:provider))
    assert len(report["sections"]) == 9 and "D3b" not in provider.calls
    provider = LearningProvider(high=True)
    with pytest.raises(AppError,match="独立审校未通过"):
        asyncio.run(generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_:None, lambda:provider))
    assert provider.calls.count("D5") == 3  # Initial review + at most two repairs.


def test_failed_stage_retry_reuses_completed_work_but_not_stale_revision():
    async def run():
        cache = {}
        failed = LearningProvider(fail_writing=True)
        with pytest.raises(AppError):
            await generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_:None, lambda:failed, cache)
        retry = LearningProvider()
        report = await generate_learning_report(pdf_bytes(), MATERIAL, {}, lambda *_:None, lambda:retry, cache)
        assert report["audit"]["overall_pass"] and not {"native","D1","D2"} & set(retry.calls)
        changed = LearningProvider()
        await generate_learning_report(pdf_bytes(), {**MATERIAL,"revision":2}, {}, lambda *_:None, lambda:changed, cache)
        assert "native" in changed.calls and "D1" in changed.calls
    asyncio.run(run())


def test_map_dependencies_and_dishonest_audit_are_rejected():
    value = mapping()
    value["knowledge_map"][0]["depends_on"] = ["K1"]
    with pytest.raises(AppError): validate_map(value)
    for severity in ["high","medium"]:
        with pytest.raises(AppError):
            validate_audit({"overall_pass":True,"scores":{f"E{i}":5 for i in range(1,9)},"issues":[{"section":"method","severity":severity,"problem":"错误","fix":"修正"}]},{"method":"内容"})


def test_tag_integrity_and_tutorial_numbers_are_distinct():
    with pytest.raises(AppError): validate_tags("D3b", "<purpose>部分输出</purpose>")
    pack = {"evidence":[{"evidence_id":"E0001","source_text":"100 samples"}]}
    assert not rule_check({"quiz":"【教学示例】自拟999个样本 [E0001]"},pack)
    assert any(x["candidate"] == "999" for x in rule_check({"experiments":"实验使用999个样本 [E0001]"},pack))
    with pytest.raises(AppError): rule_check({"method":"不存在的来源 [E9999]"},pack)


def test_runtime_schemas_fit_provider_union_parameter_limit():
    from app.reading.learning import PROMPTS
    def unions(value):
        if isinstance(value, dict):
            return int(isinstance(value.get("type"), list) or "anyOf" in value) + sum(unions(v) for v in value.values())
        return sum(unions(v) for v in value) if isinstance(value, list) else 0
    for path in PROMPTS.glob("*-schema.json"):
        assert unions(json.loads(path.read_text(encoding="utf-8"))) <= 16


def test_local_contract_rejects_missing_unknown_and_wrong_types():
    contract = {"type":"object", "properties":{"facts":{"type":"array", "items":{"type":"string"}}}, "required":["facts"], "additionalProperties":False}
    assert validate_shape({"facts":["supported"]},contract)
    for invalid in [{}, {"facts":[], "extra":"x"}, {"facts":[1]}]:
        with pytest.raises(AppError): validate_shape(invalid,contract)


def test_guide_audit_issue_actually_rewrites_guide():
    class GuideProvider(LearningProvider):
        async def read(self, system, messages):
            result = await super().read(system, messages)
            if "页面顶部的导读" in system and self.calls.count("D4") > 1:
                result.content[0].text = result.content[0].text.replace("讲解材料", "已修正的导读材料")
            return result
        async def format(self, system, messages, schema):
            result = await super().format(system,messages,schema)
            if "scores" in schema["properties"] and self.calls.count("D5") == 1:
                result.content[0].text = review_json({"overall_pass":False,"scores":{f"E{i}":4 for i in range(1,9)},"issues":[{"check":"E1","section":"quick_card","severity":"high","problem":"导读主张错误","fix":"删除错误主张"}]})
            return result
    provider=GuideProvider()
    report=asyncio.run(generate_learning_report(pdf_bytes(),MATERIAL,{},lambda *_:None,lambda:provider))
    assert report["audit"]["overall_pass"] and provider.calls.count("D4")==2


def test_provider_streams_complete_messages_and_preserves_small_grammar():
    from app.reading.provider import ClaudeProvider
    calls=[]
    final=NS(stop_reason="end_turn",content=[NS(type="text",text="{}")])
    class Stream:
        async def __aenter__(self): return self
        async def __aexit__(self,*_): pass
        async def get_final_message(self): return final
    def stream(**options):
        calls.append(options)
        return Stream()
    provider=object.__new__(ClaudeProvider)
    provider.model="synthetic-stream-test"
    provider.client=NS(messages=NS(stream=stream))
    async def run():
        assert await provider.read("system",[]) is final
        for key in ["key_equations","knowledge_map","scores"]:
            assert await provider.format("system",[],{"properties":{key:{}}}) is final
        await provider.format("system",[],{"type":"object","properties":{}})
    asyncio.run(run())
    assert all("output_config" not in call for call in calls[:-1])
    assert calls[-1]["output_config"]["format"]["type"]=="json_schema"


def test_routes_accept_known_concept_labels_but_reject_unknown_ids():
    value=mapping()
    value["routes"]["beginner"]["prerequisites_in_order"]=["K1 采样"]
    validate_map(value)
    value["routes"]["beginner"]["prerequisites_in_order"]=["K99 未定义概念"]
    with pytest.raises(AppError):validate_map(value)


def test_invalid_writing_retains_private_raw_diagnostic_without_publishing():
    class BrokenTags(LearningProvider):
        async def read(self,system,messages):
            result=await super().read(system,messages)
            if "实验怎么读" in system: result.content[0].text="不完整的实验讲解"
            return result
    artifacts={}
    with pytest.raises(AppError):
        asyncio.run(generate_learning_report(pdf_bytes(),MATERIAL,{},lambda *_:None,lambda:BrokenTags(),
            on_artifact=lambda stage,value:artifacts.update({stage:value})))
    assert artifacts['D3c-raw']=="不完整的实验讲解"


def test_map_repair_preserves_full_json_contract_and_existing_concept_ids():
    class MapRepairProvider(LearningProvider):
        async def format(self, system, messages, schema):
            if "address" in schema["properties"] and self.calls.count("D2") == 1:
                instruction=messages[0]["content"]
                assert "完整返回 D2 schema 的整个 JSON 对象" in instruction
                assert "完整返回该阶段标签" not in instruction
                assert '"knowledge_map"' in instruction and '"routes"' in instruction
                assert '"K1"' in instruction
            result=await super().format(system,messages,schema)
            if "address" in schema["properties"] and self.calls.count("D2") > 1:
                value = json.loads(result.content[0].text)
                value["knowledge_map"][0]["quick_explain"] = "【教学示例】选取部分作为样本。"
                result.content[0].text = json.dumps(value)
            if "scores" in schema["properties"] and self.calls.count("D5") == 1:
                result.content[0].text=review_json({"overall_pass":False,"scores":{f"E{i}":4 for i in range(1,9)},"issues":[{"check":"E1","section":"knowledge","severity":"medium","problem":"教学数字未标注","fix":"添加教学示例标记"}]})
            return result
    provider=MapRepairProvider()
    report=asyncio.run(generate_learning_report(pdf_bytes(),MATERIAL,{},lambda *_:None,lambda:provider))
    assert report["audit"]["overall_pass"] and provider.calls.count("D2")==2


def test_user_policy_allows_low_only_suggestions_without_rewriting():
    class SoftReviewProvider(LearningProvider):
        async def format(self, system, messages, schema):
            result=await super().format(system,messages,schema)
            if "scores" in schema["properties"]:
                result.content[0].text=review_json({"overall_pass":False,"scores":{f"E{i}":3 for i in range(1,9)},"issues":[{"check":"E3","section":"core_idea","severity":"low","problem":"比喻还可更生动","fix":"以后优化比喻"}]})
            return result
    provider=SoftReviewProvider()
    report=asyncio.run(generate_learning_report(pdf_bytes(),MATERIAL,{},lambda *_:None,lambda:provider))
    assert report["audit"]["overall_pass"] and report["audit"]["reviewer_overall_pass"] is False
    assert provider.calls.count("D5")==1 and provider.calls.count("D3a")==1
    assert "比喻还可更生动" in report["warnings"]


def test_user_policy_still_blocks_medium_issues_after_bounded_repairs():
    class MediumReviewProvider(LearningProvider):
        async def format(self, system, messages, schema):
            result=await super().format(system,messages,schema)
            if "scores" in schema["properties"]:
                result.content[0].text=review_json({"overall_pass":False,"scores":{f"E{i}":4 for i in range(1,9)},"issues":[{"check":"E1","section":"experiments","severity":"medium","problem":"教学结果冒充论文测量","fix":"标教学示例"}]})
            return result
    provider=MediumReviewProvider()
    with pytest.raises(AppError,match="教学结果冒充论文测量"):
        asyncio.run(generate_learning_report(pdf_bytes(),MATERIAL,{},lambda *_:None,lambda:provider))
    assert provider.calls.count("D5")==3


def test_rejection_without_an_issue_cannot_be_interpreted_as_pass():
    with pytest.raises(AppError,match="未列出"):
        validate_audit({"overall_pass":False,"scores":{f"E{i}":3 for i in range(1,9)},"issues":[]},{"method":"内容"})


def test_explicit_retry_resumes_latest_rejected_draft_without_rewriting_other_sections():
    class RepairedProvider(LearningProvider):
        async def read(self, system, messages):
            result = await super().read(system, messages)
            if "实验怎么读" in system:
                result.content[0].text = result.content[0].text.replace("讲解材料", "已修正的实验材料")
            return result
    async def run():
        cache={}
        failed=LearningProvider(high=True)
        with pytest.raises(AppError):
            await generate_learning_report(pdf_bytes(),MATERIAL,{},lambda *_:None,lambda:failed,cache)
        retry=RepairedProvider()
        report=await generate_learning_report(pdf_bytes(),MATERIAL,{},lambda *_:None,lambda:retry,cache)
        assert report['audit']['overall_pass'] and report['resumed_quality_review']
        assert report['audit_rounds']==1 and report['prior_audit_rounds']==3
        assert retry.calls.count('D3c')==1 and retry.calls.count('D5')==1
        assert not {'native','D1','D2','D3a','D3b','D3d','D3e'} & set(retry.calls)
        assert not any('learning-checkpoint' in key for key in cache)
    asyncio.run(run())


def test_checkpoint_cannot_resume_changed_facts_or_incomplete_writing():
    from app.reading.learning import validate_checkpoint, facts_hash
    async def run():
        cache={}
        with pytest.raises(AppError):
            await generate_learning_report(pdf_bytes(),MATERIAL,{},lambda *_:None,lambda:LearningProvider(high=True),cache)
        cp=next(value for key,value in cache.items() if 'learning-checkpoint' in key)
        cp['fact_sheet_sha256']='changed'
        with pytest.raises(AppError,match='事实底稿'):
            validate_checkpoint(cp,{},[],{'evidence':[]})
        facts=next(v for k,v in cache.items() if len(k)>5 and k[5]=='D1')
        pack=next(v for k,v in cache.items() if k[-1]=='native-evidence')
        cp['fact_sheet_sha256']=facts_hash(facts)
        cp['outputs'].pop('D3c')
        with pytest.raises(AppError,match='完整阶段'):
            validate_checkpoint(cp,facts,facts['equations'],pack)
    asyncio.run(run())
