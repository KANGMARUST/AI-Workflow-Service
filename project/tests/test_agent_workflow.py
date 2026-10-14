import os,sys,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'tests/.runs';RUN.mkdir(exist_ok=True)
temp=tempfile.TemporaryDirectory(dir=RUN)
os.environ['QUOTE_DATA_DIR']=temp.name
os.environ.pop('DATABASE_URL',None)
sys.path.insert(0,str(ROOT/'backend/.packages'));sys.path.insert(0,str(ROOT/'backend'))
import domain as d
import agent_workflow as w
from user_agent import AgentSettings,AgentError,merge_agent_result
class WorkflowTests(unittest.TestCase):
    def create_doc(self):
        import hashlib
        content=os.urandom(32);digest=hashlib.sha256(content).hexdigest()
        path=d.STORAGE/'files'/(digest+'.pdf');path.write_bytes(content)
        return d.save(d.empty_quote(dict(source_url='/api/files/'+path.name,source_name='가상.pdf',customer='가상 고객',total=100,source_total=100,source_total_kind='total')),digest=digest)
    def test_reports_keep_original_and_hide_trashed_sources(self):
        docs=[]
        for i in range(2):
            docs.append(self.create_doc())
        before=[d.get_quote(q['id']) for q in docs]
        seen=[]
        def mock(path,settings):
            self.assertTrue(path.exists());seen.append(path)
            return {'summary':'단가 차이','differences':['문서별 원문 금액 차이']},{'response_id':'job_mock'}
        result=w.execute('compare',docs,AgentSettings('FAKE_TEST_KEY','agt_test0000'),runner=mock)
        self.assertEqual(result['status'],'completed');self.assertEqual([d.get_quote(q['id']) for q in docs],before)
        self.assertFalse(seen[0].exists());self.assertIn(result['id'],[r['id'] for r in w.list_runs()])
        self.assertNotIn('FAKE_TEST_KEY',json.dumps(result))
        deleted={**docs[0],'deleted_at':d.now()};d.save(deleted,previous=docs[0])
        self.assertNotIn(result['id'],[r['id'] for r in w.list_runs()])
    def test_failed_schema_is_recorded(self):
        q=self.create_doc()
        with self.assertRaises(AgentError):w.execute('review',[q],AgentSettings('FAKE_TEST_KEY','agt_test0000'),runner=lambda *args:({'customer':'wrong role'},{}))
        self.assertEqual(w.list_runs()[0]['status'],'failed')
    def test_invalid_selection_never_calls_agent(self):
        for kind in ['bad','compare','review']:
            with self.assertRaises(AgentError):w.execute(kind,[],AgentSettings('FAKE_TEST_KEY','agt_test0000'),runner=lambda *args:self.fail('Agent must not run'))
    def test_string_items_json_mapping(self):
        q=d.empty_quote();merge_agent_result(q,{'items_json':'[{"name":"센서","unit_price":12000}]'})
        self.assertEqual(q['items'][0]['unit_price'],12000)
        with self.assertRaises(AgentError):merge_agent_result(q,{'items_json':'not JSON'})
    def test_web_endpoint_passes_request_credentials_and_rejects_missing_consent(self):
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        with patch.object(d,'backfill_document_content'),patch.object(d,'backfill_details'),patch.object(d,'backfill_people'),patch.object(d,'migrate_archive'):
            from app import app
        q=self.create_doc();client=TestClient(app)
        payload={'kind':'review','quote_ids':[q['id']]}
        self.assertEqual(client.post('/api/agent-runs',json=payload).status_code,422)
        headers={'X-User-API-Key':'FAKE_TEST_KEY','X-User-Agent-ID':'agt_review0000','X-User-Config-ID':'1','X-User-AI-Consent':'yes'}
        with patch('agent_workflow.execute',return_value={'status':'completed'}) as execute:
            result=client.post('/api/agent-runs',json=payload,headers=headers)
            self.assertEqual(result.status_code,200)
            self.assertEqual(execute.call_args.args[0],'review')
            self.assertEqual(execute.call_args.args[1][0]['id'],q['id'])
            self.assertEqual(execute.call_args.args[2].agent_id,'agt_review0000')
            self.assertEqual(execute.call_args.args[2].api_key,'FAKE_TEST_KEY')
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WorkflowTests))
    (ROOT/'tests/agent-workflow-results.json').write_text(json.dumps({'ok':result.wasSuccessful(),'tests_run':result.testsRun,'live_api_called':False}),encoding='utf-8')
    d.engine.dispose();temp.cleanup();sys.exit(not result.wasSuccessful())
