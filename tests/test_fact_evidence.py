from app.reading.fact_evidence import complete_fact_quotes


def source(quote):
    return {'evidence':[{'evidence_id':'E0006','source_text':quote,'pdf_page_start':1,'pdf_page_end_inclusive':1}]}


def fact():
    return {'fact_id':'F003','statement':'Reliable tools: 2,940 (56.8%) with scores at least 0.8.',
            'conditions':'Benchmark','numbers':['0.8','2940','56.8'],'evidence_ids':['E0006']}


def test_clipped_quote_completes_exact_sentence_without_changing_original():
    page='Tools with scores of at least 0.8 are\nmarked reliable, identifying 2,940 tools, or 56.8% of the repository.\nAnother topic.'
    original=source('Tools with scores of at least 0.8 are\n')
    output,changes=complete_fact_quotes([fact()],original,[page])
    assert len(changes)==1 and output['evidence'][0]['source_text'] in page
    assert output['evidence'][0]['source_text'].endswith('repository.')
    assert original['evidence'][0]['source_text'].endswith('are\n')


def test_no_expansion_to_new_sentence_or_unknown_number_or_page():
    for quote,page in [('Scores range to 0.8.','Scores range to 0.8. There are 2,940 tools (56.8%).'),
                       ('Scores of at least 0.8 are','Scores of at least 0.8 are reliable. Another study has 2,940 tools (56.8%).')]:
        original=source(quote)
        assert complete_fact_quotes([fact()],original,[page])==(original,[])
    original=source('Scores of at least 0.8 are')
    original['evidence'][0]['pdf_page_start']=2
    original['evidence'][0]['pdf_page_end_inclusive']=2
    assert complete_fact_quotes([fact()],original,['Scores of at least 0.8 are reliable: 2,940 (56.8%).'])==(original,[])
