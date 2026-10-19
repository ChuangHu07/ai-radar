import asyncio
import json
from types import SimpleNamespace
import pytest
from app.errors import AppError
from app.reading.overview_audit import materialize_review, validate_review, review_disputes


CARD = {'result': 'MS-SSIM exceeds baseline A.', 'title': 'Unrelated title'}
EVIDENCE = [{'evidence_id': 'E0001', 'source_text': 'MS-SSIM significantly outperformed all comparison methods, including A.'}]
ISSUE = {'check': 'C1', 'location': 'result', 'problem': 'Not every baseline was named.',
         'fix': 'Name all baselines.', 'severity': 'medium'}


def decision(**overrides):
    return {'verdict': 'not_error', 'field': 'result', 'card_quote': CARD['result'],
            'source_quotes': [{'evidence_id': 'E0001', 'quote': EVIDENCE[0]['source_text']}],
            'reason': 'The source supports the named subset of comparisons.', **overrides}


@pytest.mark.parametrize('overrides', [
    {'source_quotes': []},
    {'source_quotes': [{'evidence_id': 'E9999', 'quote': EVIDENCE[0]['source_text']}]},
    {'source_quotes': [{'evidence_id': 'E0001', 'quote': 'Invented experimental evidence'}]},
    {'field': 'title', 'card_quote': CARD['title']},
    {'card_quote': 'Not present in this card'},
])
def test_review_cannot_clear_block_without_real_field_and_source(overrides):
    with pytest.raises(AppError):
        validate_review(decision(**overrides), CARD, EVIDENCE, {'result'})


@pytest.mark.parametrize('verdict,valid,cleared', [
    ('not_error', True, True), ('confirmed_error', True, False),
    ('insufficient_evidence', True, False), ('not_error', False, False),
])
def test_second_review_keeps_uncertain_or_unverified_primary_findings(verdict, valid, cleared):
    class Provider:
        async def format_reasoned(self, *_):
            value = decision(verdict=verdict)
            value.pop('source_quotes')
            value['source_selections'] = [{'evidence_id': 'E0001' if valid else 'E9999', 'first_line': 1, 'last_line': 1}]
            return SimpleNamespace(stop_reason='end_turn', content=[SimpleNamespace(type='text', text=json.dumps(value))],
                                   usage=SimpleNamespace(input_tokens=10, output_tokens=10))
    raw = {'a': [ISSUE.copy()]}
    blocking, decisions = asyncio.run(review_disputes(Provider(), raw, {'a': CARD},
        {'a': {'evidence': EVIDENCE}}, {}, lambda *_: None))
    assert bool(decisions) == cleared
    assert bool(blocking) != cleared
    assert raw == {'a': [ISSUE]}  # Original audit is preserved.


def test_source_selections_return_exact_original_lines_and_reject_invalid_range():
    evidence = [{'evidence_id': 'E0001', 'source_text': 'first\nsecond line\nthird'}]
    review = {**decision(), 'source_selections': [{'evidence_id': 'E0001', 'first_line': 2, 'last_line': 3}]}
    assert materialize_review(review, evidence)['source_quotes'][0]['quote'] == 'second line\nthird'
    review['source_selections'][0]['last_line'] = 4
    with pytest.raises(AppError):
        materialize_review(review, evidence)
