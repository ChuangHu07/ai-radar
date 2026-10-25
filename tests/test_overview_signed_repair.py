"""A rejected numeric patch must get its bounded retry, never bypass checks."""
import asyncio
import json
from types import SimpleNamespace as NS
import pytest
from app.errors import AppError
from app.reading.overview import generate_overview, TAGS

@pytest.mark.parametrize('correct_second_patch', [True, False])
def test_signed_result_patch_retry_and_no_invalid_publication(correct_second_patch):
    patches=[]; artifacts={}; audit_calls=[]
    def message(value):
        return NS(stop_reason='end_turn',content=[NS(type='text',text=value)],usage=NS(input_tokens=1,output_tokens=1))
    class Provider:
        model='synthetic-signed-repair-test'
        async def __aenter__(self): return self
        async def __aexit__(self,*_): pass
        async def read(self,*_):
            return message(''.join(f'<{tag}>'+('decrease 45.3 [E0001]' if tag=='result' else f'Synthetic {tag} [E0001]')+f'</{tag}>' for tag in TAGS))
        async def format(self,system,messages,schema):
            props=schema['properties']
            if 'key_results' in props:
                value={'arxiv_id':'a','work_type':{'primary':'synthetic','secondary':None},'problem':'synthetic','why_hard':'synthetic',
                    'pain_scenario':None,'core_idea':'synthetic','key_mechanism':'synthetic','key_results':[{'claim':'change -45.3','number':'-45.3',
                    'compared_to':None,'setting':None,'source':'arxiv_abstract','evidence_ids':['E0001']}],
                    'address_hint':{'direction':'synthetic','route':'synthetic','contribution':'synthetic'},'neighbors':[],
                    'limitations':None,'signals':{'code_available':None,'venue':None,'experiment_scale':None},'confidence_notes':'synthetic','evidence_ids':['E0001']}
            elif 'title' in props:
                patches.append(messages[0]['content'])
                value={tag:None for tag in TAGS}
                value['result']='change -45.3 [E0001]' if correct_second_patch and len(patches)==2 else 'still decrease 45.3 [E0001]'
                if len(patches)==2: assert '上次定点修订仍未通过' in patches[-1]
            else:
                audit_calls.append(True)
                value={'results':[{'arxiv_id':'a','pass':True,'issues':[]}]}
            return message(json.dumps(value))
    paper={'paper_id':'a','arxiv_id':'av1','title':'Synthetic','authors':[],'categories':['cs.AI'],'comments':None,
        'summary':'change -45.3','source_url':'https://arxiv.org/abs/a','basis':'abstract'}
    run=generate_overview([paper],{},lambda *_:None,provider_factory=Provider,
        on_artifact=lambda name,value:artifacts.update({name:value}))
    if correct_second_patch:
        report=asyncio.run(run)
        card=report['papers'][0]['card']
        assert card['result']=='change -45.3 [E0001]'
        assert card['title']=='Synthetic title [E0001]'
        assert audit_calls==[True]
    else:
        with pytest.raises(AppError,match='45.3'): asyncio.run(run)
        assert audit_calls==[]
    assert len(patches)==2
    assert 'S3-field-rejected-a-1' in artifacts
