"""Language variants derived from the audited Chinese report, retaining evidence."""
from collections import Counter
from copy import deepcopy
import json
import re
from hashlib import sha256

from ..errors import AppError
from .provider import ModelProvider, add_usage, complete_text, cache_model

LANGUAGES = {'zh', 'en', 'bilingual'}
MATH = re.compile(r'(?<!\\)\$\$[\s\S]*?(?<!\\)\$\$|(?<!\\)\$[^\n$]+?(?<!\\)\$|\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]')
CODE = re.compile(r'^```[^\n]*\n[\s\S]*?^```[ \t]*$', re.M)
CITATION = re.compile(r'\[E\d{4}\]')
NUMBERS = re.compile(r'(?<![A-Za-z])\d+(?:[.,]\d+)?')
LINK_TARGET = re.compile(r'\]\((#[^)]+)\)')
HEADING = re.compile(r'^(#{1,6})\s', re.M)
CJK = re.compile(r'[\u3400-\u9fff]')
IDENTIFIER = re.compile(r'(?<![A-Za-z0-9_])(?:E\d{4}|[RCKDFQS]\d+(?:\.\d+)*|Eq\.\s*\d+)(?![A-Za-z0-9_])')
PROTECTED = re.compile('|'.join(f'(?:{pattern.pattern})' for pattern in (CODE, MATH, CITATION, LINK_TARGET, IDENTIFIER, NUMBERS)), re.M)
KEEP = re.compile(r'__KEEP_\d{4}__')


def _mask_protected(source):
    values = []

    def replace(match):
        token = f'__KEEP_{len(values):04d}__'
        values.append((token, match.group()))
        return token

    return PROTECTED.sub(replace, source), values


def _restore_protected(translated, values):
    if Counter(KEEP.findall(translated)) != Counter(token for token, _ in values):
        raise AppError('LANGUAGE_OUTPUT_INVALID', '语言转换遗漏或改写了必须保留的数字、公式或引用；原报告仍可查看。', 502, True)
    for token, original in values:
        translated = translated.replace(token, original, 1)
    return translated


def _validate(original, translated, english=False):
    if not translated.strip() or ('```'==translated.strip()[:3] and not original.strip().startswith('```')) or '__KEEP_' in translated:
        raise AppError('LANGUAGE_OUTPUT_INVALID', '语言版本为空或包含代码围栏；原报告仍可查看。', 502, True)
    for pattern in (CODE, MATH, CITATION, NUMBERS, LINK_TARGET, IDENTIFIER):
        if Counter(pattern.findall(original)) != Counter(pattern.findall(translated)):
            raise AppError('LANGUAGE_OUTPUT_INVALID', '语言转换改变了公式、引用编号或数字；原报告仍可查看。', 502, True)
    if HEADING.findall(original) != HEADING.findall(translated):
        raise AppError('LANGUAGE_OUTPUT_INVALID', '语言转换改变了 Markdown 栏目层级；原报告仍可查看。', 502, True)
    if english and CJK.search(MATH.sub('', CODE.sub('', translated))):
        raise AppError('LANGUAGE_OUTPUT_INVALID', '英文版本仍含有未译的中文；原报告仍可查看。', 502, True)


def _targets(report):
    """Yield mutable parent/key pairs for prose only; source text and IDs stay exact."""
    if report['mode'] == 'overview':
        batch = report['batch']
        for address in batch['shared_address'].values():
            if not isinstance(address, dict):
                continue
            for key in ('name', 'tension'):
                if key in address:
                    yield address, key
        yield batch, 'map_summary'
        for index, _ in enumerate(batch.get('highlights', [])):
            yield batch['highlights'], index
        for cluster in batch.get('clusters', []):
            for key in ('name', 'what_is_happening'):
                if key in cluster:
                    yield cluster, key
        for rating in batch.get('ratings', []):
            if 'reason' in rating:
                yield rating, 'reason'
        for relation in batch.get('relations', []):
            if 'note' in relation:
                yield relation, 'note'
        for paper in report['papers']:
            for key in ('title', 'plain', 'address', 'one_liner', 'pain', 'trick', 'result', 'so_what', 'caveat', 'tags'):
                if key in paper['card']:
                    yield paper['card'], key
            for index, _ in enumerate(paper.get('source_warnings', [])):
                yield paper['source_warnings'], index
        # Raw audit drafts are diagnostic evidence, not displayed report prose.
        # Preserve them verbatim, including superseded findings and decisions.
    else:
        # Keep an original paper title intact; generated Chinese joint titles
        # belong to the report prose and should follow the report language.
        if CJK.search(report.get('title', '')):
            yield report, 'title'
        for section in report['sections']:
            yield section['narrative'], 'zh'
        for fact in report.get('facts', []):
            for key in ('statement', 'conditions'):
                yield fact, key
        for index, _ in enumerate(report.get('warnings', [])):
            yield report['warnings'], index
        learning = report.get('learning_map') or {}
        for concept in learning.get('knowledge_map', []):
            for key in ('term', 'why_needed', 'enough_standard', 'quick_explain'):
                yield concept, key
            for key in ('q', 'a'):
                yield concept['self_check'], key
        for route in learning.get('routes', {}).values():
            for key in ('estimated_time', 'paper_reading_order'):
                yield route, key
            for key in ('prerequisites_in_order', 'focus', 'skip'):
                for index, _ in enumerate(route.get(key, [])):
                    yield route[key], index
        for concept in learning.get('knowledge_map', []):
            for index, _ in enumerate(concept.get('learn_from', [])):
                yield concept['learn_from'], index


def _split_prose(text, limit=1800):
    """Split at paragraph boundaries, never within a protected math span."""
    spans=[(m.start(),m.end()) for pattern in (MATH,CODE) for m in pattern.finditer(text)]
    cuts=[m.end() for m in re.finditer(r'\n\n',text)
          if not any(first<m.end()<last for first,last in spans)]
    parts=[];start=0
    while len(text)-start>limit:
        nearby=[cut for cut in cuts if start<cut<=start+limit]
        if nearby:cut=max(nearby)
        else:
            later=[cut for cut in cuts if cut>start]
            if not later:break
            cut=min(later)
        parts.append(text[start:cut]);start=cut
    parts.append(text[start:])
    return parts


async def translate_report(base_report, language, usage, on_phase, provider_factory=ModelProvider, cache=None, on_artifact=None):
    if language not in LANGUAGES:
        raise AppError('INVALID_LANGUAGE', '报告语言不受支持。', 422)
    report = deepcopy(base_report)
    cache = cache if cache is not None else {}
    def save(label, value):
        if on_artifact: on_artifact(label, value)
    if language == 'zh':
        return report
    targets = [(parent, key) for parent, key in _targets(report) if isinstance(parent[key], str) and parent[key].strip()]
    assembled=[];expanded=[]
    for parent,key in targets:
        original=parent[key]
        parts=_split_prose(original)
        if len(parts)==1:expanded.append((parent,key));continue
        wrappers=[{'part':part} for part in parts]
        assembled.append((parent,key,original,parts,wrappers))
        expanded.extend((wrapper,'part') for wrapper in wrappers)
    targets=expanded
    batches = []
    current = []
    size = 0
    for target in targets:
        length = len(target[0][target[1]])
        if current and (len(current) >= 8 or size + length > 5000):
            batches.append(current)
            current, size = [], 0
        current.append(target)
        size += length
    if current:
        batches.append(current)
    async with provider_factory() as provider:
        if hasattr(provider, 'bind_usage'):
            provider.bind_usage(usage)
        completed = 0
        for group in batches:
            originals = [parent[key] for parent, key in group]
            masked = [_mask_protected(source) for source in originals]
            keys = [(cache_model(provider), 'translation-protected-v2', sha256(source.encode()).hexdigest()) for source in originals]
            if all(key in cache for key in keys):
                translations = [cache[key] for key in keys]
            else:
                translations = None
            completed += len(group)
            on_phase(f'转换报告语言 · {completed}/{len(targets)}')
            schema = {'type': 'object', 'properties': {'texts': {'type': 'array', 'items': {'type': 'string'}}},
                      'required': ['texts'], 'additionalProperties': False}
            message = None if translations is not None else await provider.format(
                'Translate each Chinese research explanation into clear English, preserving Markdown, all citation IDs, '
                'all numerals, and every LaTeX expression byte-for-byte. Never add or remove claims. '
                'Only tokens actually present in each input item stand for protected source spans: keep each exactly once, '
                'in the same order, without editing it. Do not leave Chinese words in the English translation. '
                'Keep bare evidence and rule IDs unchanged. Translate Chinese number words using English words '
                '(for example, 三维 as three-dimensional, never 3D). Never introduce new digit numerals. '
                'Translate quoted Chinese phrases in this report prose as ordinary English prose. '
                'Do not create new placeholder tokens. Return JSON {"texts": [...]} in the same order and length.',
                [{'role': 'user', 'content': json.dumps({'texts': [source for source, _ in masked],
                    'allowed_tokens_per_item':[[token for token,_ in values] for _,values in masked]}, ensure_ascii=False)}], schema)
            if message is not None: add_usage(usage, message)
            try:
                if message is not None: translations = json.loads(complete_text(message))['texts']
                if len(translations) != len(group) or any(not isinstance(s, str) for s in translations):
                    raise ValueError('wrong translation count')
            except (ValueError, TypeError, KeyError) as exc:
                raise AppError('LANGUAGE_OUTPUT_INVALID', '模型未按固定栏目返回完整语言版本；原报告仍可查看。', 502, True) from exc
            for (parent, key), original, translated, (masked_source, protected), field_key in zip(group, originals, translations, masked, keys):
                try:
                    if field_key in cache:
                        translated = cache[field_key]
                    else:
                        translated = _restore_protected(translated, protected)
                    _validate(original, translated, english=True)
                except AppError as first_error:
                    save('language-rejected-' + field_key[-1], {'original': original, 'translated': translated,
                         'error': first_error.payload(), 'masked_source': masked_source})
                    # Retry only the offending prose field; accepted fields and source data stay untouched.
                    on_phase(f'修复英文段落 · {completed}/{len(targets)}')
                    repair = await provider.format(
                        'Translate this one Chinese research explanation into fluent English. Return exactly one '
                        'JSON texts item. Preserve each __KEEP_ token exactly once, without adding, deleting, '
                        'or editing token characters. Preserve Markdown heading levels. Do not leave Chinese words. '
                        'Never alter the scientific claim or translate source quotations.',
                        [{'role': 'user', 'content': json.dumps({'texts': [masked_source],
                          'instructions': 'Do not introduce new digits; spell translated Chinese counts as words. Keep every bare ID unchanged.',
                          'allowed_tokens':[token for token,_ in protected],
                          'previous_error': first_error.message}, ensure_ascii=False)}], schema)
                    add_usage(usage, repair)
                    try:
                        repaired = json.loads(complete_text(repair))['texts']
                        if len(repaired) != 1 or not isinstance(repaired[0], str):
                            raise ValueError('wrong repair count')
                    except (ValueError, TypeError, KeyError) as exc:
                        raise AppError('LANGUAGE_OUTPUT_INVALID', '英文段落定点修复未按格式返回；原报告仍可查看。', 502, True) from exc
                    try:
                        translated = _restore_protected(repaired[0], protected)
                        _validate(original, translated, english=True)
                    except AppError as final_error:
                        save('language-repair-rejected-'+field_key[-1], {'original':original,
                            'translated':repaired[0], 'masked_source':masked_source, 'error':final_error.payload()})
                        raise
                cache[field_key] = translated
                save('language-cache', [{'key': list(k), 'text': value} for k, value in cache.items()])
                if report['mode'] != 'overview' and key == 'zh' and parent is not report:
                    parent['en'] = translated
                else:
                    parent[key] = translated if language == 'en' else original + '\n\nEnglish: ' + translated
    for parent,key,original,parts,wrappers in assembled:
        translated=''.join(wrapper['part'] if language=='en' else wrapper['part'][len(part)+len('\n\nEnglish: '):]
                           for part,wrapper in zip(parts,wrappers))
        _validate(original,translated,english=True)
        if report['mode']!='overview' and key=='zh' and parent is not report:parent['en']=translated
        else:parent[key]=translated if language=='en' else original+'\n\nEnglish: '+translated
    report['language'] = language
    report['translation_model'] = provider.model
    report['translation_provider'] = getattr(provider, 'provider', 'unknown')
    report['source_report_id'] = base_report.get('source_report_id', base_report.get('report_id'))
    return report
