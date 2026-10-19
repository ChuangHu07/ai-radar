from fastapi.testclient import TestClient
from app.main import create_app
from test_overview import Source, start, wait
from pdf_factory import pdf_bytes


def test_retrieved_pdf_and_uploaded_pdf_share_readiness_and_replacement_rules():
    async def overview(papers,*args,**kwargs):
        return {'mode':'overview','papers':[],'synthetic_test':True}
    with TestClient(create_app(source=Source(count=1),overview_generate=overview)) as client:
        job=wait(client,start(client),{'succeeded','failed'})
        assert job['status']=='succeeded'
        collection=client.post('/api/v1/collections',json={'from_overview_job_id':job['job_id'],
            'selected_paper_ids':['2610.00000']}).json()['data']
        path='/api/v1/collections/'+collection['collection_id']
        assert collection['materials'][0]['origin']=='arxiv'
        collection=client.post(path+'/uploads',data={'expected_revision':collection['revision']},
            files={'files':('local.pdf',b'invalid','application/pdf')}).json()['data']
        assert collection['derived_mode']=='joint' and not collection['can_generate']
        failed=collection['materials'][1]
        collection=client.put(path+'/materials/'+failed['material_id']+'/file',
            data={'expected_revision':collection['revision']},
            files={'file':('repaired.pdf',pdf_bytes(),'application/pdf')}).json()['data']
        assert collection['materials'][1]['material_id']==failed['material_id']
        assert collection['can_generate'] and collection['derived_mode']=='joint'
        assert {m['origin'] for m in collection['materials']}=={'arxiv','upload'}
