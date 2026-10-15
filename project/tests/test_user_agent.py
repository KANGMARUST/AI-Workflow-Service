"""No live keys or network. Verify request credentials, fixed provider, and safe errors."""
import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]
RUN_ROOT=(ROOT/'tests/.runs').resolve();RUN_ROOT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'backend/.packages'));sys.path.insert(0,str(ROOT/'backend'))
import httpx
from starlette.requests import Request
from user_agent import AgentSettings,AgentError,settings_from_request,run_agent,scrub


class UserAgentTests(unittest.TestCase):
    def temporary(self):
        result=tempfile.TemporaryDirectory(prefix='user-api-',dir=RUN_ROOT)
        if not Path(result.name).resolve().is_relative_to(RUN_ROOT):raise RuntimeError('Test directory outside workspace')
        return result
    def request(self,headers=None,scheme='https',host='quote.example'):
        return Request({'type':'http','scheme':scheme,'path':'/api/upload','server':(host,443),'headers':[(b'host',host.encode())]+[(k.lower().encode(),str(v).encode()) for k,v in (headers or {}).items()]})

    def test_environment_key_is_never_selected(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'FAKE_SHARED_KEY','UPSTAGE_API_KEY':'FAKE_OTHER_SHARED_KEY','EXTERNAL_AI_ENABLED':'true'}):
            self.assertIsNone(settings_from_request(self.request()))
        self.assertNotIn('api_key',repr(AgentSettings('FAKE_ONLY_MEMORY_KEY','agt_test0000')))

    def test_consent_transport_validation_and_no_key_echo(self):
        headers={'X-User-API-Key':'FAKE_USER_TOKEN_12345','X-User-Agent-ID':'agt_test0000','X-User-AI-Consent':'yes','X-User-Config-ID':'2'}
        config=settings_from_request(self.request(headers));self.assertEqual(config.config_id,'2')
        self.assertEqual(config.api_key,headers['X-User-API-Key'])
        for modified,scheme in [({**headers,'X-User-AI-Consent':'no'},'https'),({**headers,'X-User-Agent-ID':'wrong'},'https'),(headers,'http')]:
            with self.assertRaises(AgentError) as error:settings_from_request(self.request(modified,scheme))
            self.assertNotIn(headers['X-User-API-Key'],str(error.exception))

    def test_two_users_keep_independent_headers_and_cleanup_files(self):
        with self.temporary() as temp:
            path=Path(temp)/'test.pdf';path.write_bytes(b'%PDF fake mock input')
            def execute(token):
                seen=[]
                def handle(request):
                    self.assertEqual(request.url.host,'api.upstage.ai');self.assertTrue(request.url.path.startswith('/v2/'))
                    self.assertEqual(request.headers['Authorization'],'Bearer '+token);seen.append((request.method,request.url.path))
                    if request.url.path=='/v2/files' and request.method=='POST':return httpx.Response(200,json={'id':'file_mock'})
                    if request.url.path=='/v2/responses':
                        body=json.loads(request.content);self.assertEqual(body['model'],'agt_test0000');self.assertEqual(body['config_id'],'1')
                        return httpx.Response(200,json={'id':'resp_mock','status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps({'customer':'가상 고객','api_key':token,'notes':'secret '+token})}]}]})
                    if request.method=='DELETE':return httpx.Response(200,json={'deleted':True})
                    self.fail('unexpected request')
                result,metadata=run_agent(path,AgentSettings(token,'agt_test0000'),transport=httpx.MockTransport(handle))
                self.assertNotIn(token,json.dumps(result));self.assertNotIn('api_key',result);self.assertEqual(result['customer'],'가상 고객')
                self.assertIn(('DELETE','/v2/files/file_mock'),seen);return metadata
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(execute,['FAKE_USER_A_TOKEN','FAKE_USER_B_TOKEN']))
            self.assertEqual(len(results),2)

    def test_provider_errors_hide_response_and_credentials(self):
        key='FAKE_SECRET_TOKEN'
        with self.temporary() as temp:
            path=Path(temp)/'test.pdf';path.write_bytes(b'%PDF fake')
            transport=httpx.MockTransport(lambda request:httpx.Response(401,json={'error':key}))
            with self.assertRaises(AgentError) as error:run_agent(path,AgentSettings(key,'agt_test0000'),transport=transport)
            self.assertNotIn(key,str(error.exception));self.assertIn('인증',str(error.exception))

    def test_original_file_types_are_uploaded_with_matching_names_and_content_types(self):
        types={'.pdf':'application/pdf','.xls':'application/vnd.ms-excel','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg'}
        with self.temporary() as temp:
            for extension,mime in types.items():
                path=Path(temp)/('virtual'+extension);path.write_bytes(b'virtual document')
                def handle(request):
                    if request.url.path=='/v2/files' and request.method=='POST':
                        body=request.content
                        self.assertIn(('filename="quotation'+extension+'"').encode(),body)
                        self.assertIn(('Content-Type: '+mime).encode(),body)
                        return httpx.Response(200,json={'id':'file_mock'})
                    if request.url.path=='/v2/responses':return httpx.Response(200,json={'id':'job_mock','status':'completed','output_text':'{"customer":"가상 고객"}'})
                    if request.method=='DELETE':return httpx.Response(200,json={'deleted':True})
                    self.fail('unexpected request')
                result,_=run_agent(path,AgentSettings('FAKE_TEST_KEY','agt_test0000'),transport=httpx.MockTransport(handle))
                self.assertEqual(result['customer'],'가상 고객')

    def test_polling_and_timeout_cleanup(self):
        with self.temporary() as temp:
            path=Path(temp)/'test.pdf';path.write_bytes(b'%PDF fake');seen=[]
            def handle(request):
                seen.append((request.method,request.url.path))
                if request.url.path=='/v2/files':return httpx.Response(200,json={'id':'file_poll'})
                if request.method=='POST':return httpx.Response(200,json={'id':'resp_poll','status':'queued'})
                if request.method=='DELETE':return httpx.Response(200,json={})
                return httpx.Response(200,json={'status':'completed','output_text':'{"customer":"가상 고객"}'})
            with patch('user_agent.time.sleep'):
                result,_=run_agent(path,AgentSettings('FAKE_USER_TOKEN','agt_test0000'),transport=httpx.MockTransport(handle))
            self.assertEqual(result['customer'],'가상 고객');self.assertIn(('GET','/v2/responses/resp_poll'),seen)
            with self.assertRaises(AgentError):run_agent(path,AgentSettings('FAKE_USER_TOKEN','agt_test0000'),transport=httpx.MockTransport(handle),timeout=-1)
            self.assertIn(('DELETE','/v2/files/file_poll'),seen)

    def test_two_input_files_are_sent_together_and_cleaned(self):
        with self.temporary() as temp:
            paths=[Path(temp)/'original.pdf',Path(temp)/'extracted.pdf']
            for path in paths:path.write_bytes(b'%PDF invented')
            uploads=[];deleted=[]
            def handle(request):
                if request.url.path=='/v2/files' and request.method=='POST':
                    ident='file_'+str(len(uploads)+1);uploads.append(ident)
                    self.assertIn(('quotation-'+str(len(uploads))+'.pdf').encode(),request.content)
                    return httpx.Response(200,json={'id':ident})
                if request.url.path=='/v2/responses':
                    body=json.loads(request.content)
                    self.assertEqual(body['input'][0]['content'],[{'type':'input_file','file_id':ident} for ident in uploads])
                    return httpx.Response(200,json={'id':'response_mock','status':'completed','output_text':'{"summary":"가상 결과"}'})
                if request.method=='DELETE':deleted.append(request.url.path);return httpx.Response(200,json={})
                self.fail('unexpected request')
            result,_=run_agent(paths,AgentSettings('FAKE_USER_TOKEN','agt_test0000'),transport=httpx.MockTransport(handle))
            self.assertEqual(result['summary'],'가상 결과')
            self.assertEqual(deleted,['/v2/files/file_1','/v2/files/file_2'])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(UserAgentTests))
    (ROOT/'tests/user-api-results.json').write_text(json.dumps({'ok':result.wasSuccessful(),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'live_api_called':False},indent=2),encoding='utf-8')
    sys.exit(not result.wasSuccessful())
