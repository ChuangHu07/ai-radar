import xml.etree.ElementTree as ET
import pytest
from app.reading.overview_scene import validate_scene, render_scene
import asyncio
import json
from types import SimpleNamespace as NS
from app.reading.overview_scene import generate_scene


def scene():
    return {'steps':[{'icon':icon,'label_zh':'查看细胞信息','label_en':'Inspect cell information',
                     'evidence_ids':['E0001']} for icon in ['cells','network','document']]}


def test_scene_is_offline_svg_and_has_no_executable_markup():
    value=scene()
    validate_scene(value,[{'evidence_id':'E0001'}])
    for language in ['zh','en']:
        root=ET.fromstring(render_scene(value,language))
        assert root.tag.endswith('svg')
        assert all(not node.tag.endswith(('script','foreignObject')) for node in root.iter())
    value['steps'][0]['label_en']='Cells & tissues'
    ET.fromstring(render_scene(value,'en'))


def test_scene_rejects_unknown_sources_and_invented_measured_labels():
    value=scene()
    with pytest.raises(ValueError):validate_scene(value,[{'evidence_id':'E0002'}])
    value['steps'][0]['label_en']='Accuracy improves 50%'
    with pytest.raises(ValueError):validate_scene(value,[{'evidence_id':'E0001'}])


@pytest.mark.parametrize('passed',[True,False])
def test_scene_factual_review_blocks_unsupported_actions(passed):
    class Provider:
        model='synthetic-test-only'
        async def format(self,system,messages,schema):
            value=scene() if 'steps' in schema['properties'] else {'passed':passed,'issues':[] if passed else ['Simulation was presented as patient data collection']}
            return NS(stop_reason='end_turn',content=[NS(type='text',text=json.dumps(value))],usage=NS(input_tokens=1,output_tokens=1))
    task=generate_scene(Provider(),{'title':'Synthetic paper'},{'plain':'Synthetic','trick':'Synthetic'},
        [{'evidence_id':'E0001','source_text':'Synthetic simulation only'}],{})
    if passed:assert asyncio.run(task)['scene_version']==3
    else:
        with pytest.raises(ValueError,match='patient data'):asyncio.run(task)


def test_scene_can_repair_a_failed_audit_once_and_cache_only_the_passed_result():
    class Provider:
        model='synthetic-test-only'
        calls=0
        audits=0
        async def format(self,system,messages,schema):
            self.calls+=1
            if 'steps' in schema['properties']:
                value=scene();value['steps'][0]['label_en']='Inspect 3D cell information'
            else:
                self.audits+=1
                value={'passed':self.audits==2,'issues':[] if self.audits==2 else ['Use simulated input rather than patient recordings']}
            return NS(stop_reason='end_turn',content=[NS(type='text',text=json.dumps(value))],usage=NS(input_tokens=1,output_tokens=1))
    provider=Provider();cache={};artifacts={}
    args=(provider,{'title':'Synthetic'},{'plain':'Synthetic','trick':'Synthetic'},[{'evidence_id':'E0001','source_text':'Synthetic'}],{})
    output=asyncio.run(generate_scene(*args,cache=cache,on_artifact=lambda k,v:artifacts.update({k:v})))
    assert output['scene_audit']=={'passed':True,'issues':[]}
    assert 'three-dimensional' in output['scene']['steps'][0]['label_en']
    assert 'scene-rejected-attempt-1' in artifacts and provider.calls==4
    assert asyncio.run(generate_scene(*args,cache=cache))==output and provider.calls==4
