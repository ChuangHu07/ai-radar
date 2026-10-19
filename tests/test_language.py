import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from app.errors import AppError
from app.reading.language import _validate, translate_report


class FakeProvider:
    model = 'fake'

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def format(self, system, messages, schema):
        originals = json.loads(messages[0]['content'])['texts']
        substitutions = {'联合': 'Joint ', '研究': 'research ', '证据': 'evidence', '报告': 'report',
                         '领域': 'field', '问题': 'problem', '方向': 'direction', '难点': 'challenge',
                         '进展': 'progress', '为': 'is', '条件': 'condition', '基础': 'basics',
                         '课程': 'course'}
        translated = []
        for source in originals:
            for chinese, english in substitutions.items():
                source = source.replace(chinese, english)
            translated.append(source)
        return NS(stop_reason='end_turn', content=[NS(type='text', text=json.dumps({'texts': translated}))],
                  usage=NS(input_tokens=10, output_tokens=10))


def report():
    return {'mode': 'single', 'language': 'zh', 'report_id': 'original',
            'sections': [{'key': 'method', 'narrative': {'zh': '研究证据 [E0001] 为 $x=2$。'},
                          'fact_ids': ['F1'], 'evidence_ids': ['E0001']}],
            'facts': [{'statement': '研究证据 2', 'conditions': '研究条件', 'evidence_ids': ['E0001']}],
            'warnings': [], 'evidence': [{'evidence_id': 'E0001', 'source_text': 'Original source evidence 2'}]}


@pytest.mark.parametrize('language', ['en', 'bilingual'])
def test_language_variant_retains_evidence_and_facts(language):
    source = report()
    output = asyncio.run(translate_report(source, language, {}, lambda _: None, FakeProvider))
    assert source['sections'][0]['narrative'] == {'zh': '研究证据 [E0001] 为 $x=2$。'}
    assert output['evidence'] == source['evidence']
    assert output['sections'][0]['narrative']['en'] == 'research evidence [E0001] is $x=2$。'
    assert output['language'] == language
    assert output['source_report_id'] == 'original'


class BrokenProvider(FakeProvider):
    async def format(self, system, messages, schema):
        response = await super().format(system, messages, schema)
        response.content[0].text = response.content[0].text.replace('__KEEP_0000__', '__KEEP_9999__')
        return response


def test_long_sections_split_and_reassemble_without_losing_protected_spans():
    source=report()
    source['sections'][0]['narrative']['zh']='研究证据 [E0001] 为 $x=2$。\n\n'*120
    output=asyncio.run(translate_report(source,'en',{},lambda _:None,FakeProvider))
    assert output['sections'][0]['narrative']['en']=='research evidence [E0001] is $x=2$。\n\n'*120
    assert output['evidence']==source['evidence']


def test_english_preserves_chinese_inside_literal_math_but_rejects_residual_tokens():
    _validate('$\\text{输入}=2$','$\\text{输入}=2$',english=True)
    with pytest.raises(AppError):_validate('English','English __KEEP_x__',english=True)


def test_literal_code_blocks_are_kept_intact_in_english_reports():
    from app.reading.language import _mask_protected, _restore_protected, _split_prose
    source='```python\nx = 40e6  # 原始代码\n\ny = x / 2\n```'
    masked,values=_mask_protected(source)
    assert len(values)==1
    assert _restore_protected(masked,values)==source
    assert _split_prose(source,10)==[source]
    _validate(source,source,english=True)


def test_ids_adjacent_to_chinese_have_same_boundaries_as_english():
    from app.reading.language import _mask_protected
    _validate('基于R1-Zero设置 [E0022]','Based on R1-Zero settings [E0022]',english=True)
    masked,values=_mask_protected('基于R1-Zero设置 [E0022]')
    assert any(value=='R1' for _,value in values)
    with pytest.raises(AppError):_validate('基于R1-Zero设置 [E0022]','Based on R2-Zero settings [E0022]',english=True)


def test_language_variant_rejects_changed_citations():
    with pytest.raises(AppError) as exc:
        asyncio.run(translate_report(report(), 'en', {}, lambda _: None, BrokenProvider))
    assert exc.value.code == 'LANGUAGE_OUTPUT_INVALID'


class FlakyProvider(FakeProvider):
    calls = 0

    async def format(self, system, messages, schema):
        self.calls += 1
        response = await super().format(system, messages, schema)
        if self.calls == 1:
            response.content[0].text = response.content[0].text.replace('__KEEP_0000__', '__KEEP_9999__')
        return response


def test_language_retries_only_a_failed_prose_field():
    output = asyncio.run(translate_report(report(), 'en', {}, lambda _: None, FlakyProvider))
    assert output['sections'][0]['narrative']['en'] == 'research evidence [E0001] is $x=2$。'
    assert output['evidence'] == report()['evidence']


def test_bilingual_overview_preserves_paper_identity_and_source_quote():
    source = {'mode': 'overview', 'language': 'zh', 'report_id': 'overview-base',
              'batch': {'shared_address': {'earth': {'name': '研究领域', 'tension': '研究问题'},
                                           'country': {'name': '研究方向', 'tension': '研究难点'}},
                        'map_summary': '研究证据 [E0001]', 'highlights': ['研究进展'],
                        'clusters': [], 'ratings': [], 'relations': []},
              'papers': [{'paper_id': '2610.00001', 'arxiv_id': '2610.00001',
                          'card': {key: '研究证据 [E0001]' for key in
                                   ('title', 'plain', 'address', 'one_liner', 'pain', 'trick', 'result', 'so_what', 'caveat', 'tags')},
                          'evidence': [{'evidence_id': 'E0001', 'source_text': 'Original quote'}]}],
              'audit': {'results': []}}
    output = asyncio.run(translate_report(source, 'bilingual', {}, lambda _: None, FakeProvider))
    assert output['papers'][0]['paper_id'] == source['papers'][0]['paper_id']
    assert output['papers'][0]['evidence'] == source['papers'][0]['evidence']
    assert 'English:' in output['papers'][0]['card']['one_liner']
    assert 'English:' in output['papers'][0]['card']['plain']


def test_reading_title_and_learning_resources_follow_report_language():
    source = report()
    source['title'] = '联合研究报告'
    source['learning_map'] = {'knowledge_map': [{'term': '研究', 'why_needed': '研究证据',
        'enough_standard': '研究基础', 'quick_explain': '', 'self_check': {'q': '研究?', 'a': '证据'},
        'learn_from': ['研究课程 / evidence'], 'depends_on': []}], 'routes': {}}
    english = asyncio.run(translate_report(source, 'en', {}, lambda _: None, FakeProvider))
    assert english['title'] == 'Joint research report'
    assert english['learning_map']['knowledge_map'][0]['learn_from'] == ['research course / evidence']
    assert source['learning_map']['knowledge_map'][0]['learn_from'] == ['研究课程 / evidence']


def test_language_rejects_changed_markdown_heading_levels():
    with pytest.raises(AppError) as exc:
        _validate('## 研究\n### 证据', '### Research\n## Evidence')
    assert exc.value.code == 'LANGUAGE_OUTPUT_INVALID'


def test_translation_cache_reuses_only_identical_source_fields():
    class NoCalls(FakeProvider):
        async def format(self, *_):
            raise AssertionError('Validated unchanged fields must not call the model again')
    cache = {}
    first = asyncio.run(translate_report(report(), 'en', {}, lambda _: None, FakeProvider, cache=cache))
    second = asyncio.run(translate_report(report(), 'bilingual', {}, lambda _: None, NoCalls, cache=cache))
    assert second['sections'][0]['narrative']['en'] == first['sections'][0]['narrative']['en']
    assert second['evidence'] == report()['evidence']


def test_bare_evidence_and_rule_ids_are_protected_as_whole_spans():
    from app.reading.language import _mask_protected, _restore_protected
    source = 'E0001 C1 K12 Eq.2'
    masked, spans = _mask_protected(source)
    assert [span for _, span in spans] == ['E0001', 'C1', 'K12', 'Eq.2']
    restored = _restore_protected(masked, spans)
    _validate(source, restored, english=True)
    with pytest.raises(AppError):
        _restore_protected(masked.replace('__KEEP_0001__', 'C 1'), spans)
