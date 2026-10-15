"""Invented documents, isolated DB and mocked Studio; no provider call."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend/.packages'),str(ROOT/'backend')]
RUNS=ROOT/'tests/.runs';RUNS.mkdir(exist_ok=True)
TEMP=tempfile.TemporaryDirectory(prefix='submission-',dir=RUNS)
os.environ['QUOTE_DATA_DIR']=TEMP.name
os.environ['DATABASE_URL']='sqlite:///'+(Path(TEMP.name)/'quotes.db').as_posix()

import domain as d
from fastapi import BackgroundTasks
from starlette.requests import Request
from app import start_analysis_flow
from submission_workflow import start,run,get,normalized_extraction,checked_evidence
from user_agent import AgentError

AGENTS={role:{'agent_id':'agt_fake_'+role,'config_id':'1'} for role in ('extract','review','compare')}


def row(name='모듈',**values):
    item={'name':name,'model':'M-10','specification':'10 mm','unit':'개','quantity':2,'unit_price':120,'amount':240,
          'is_component':False,'parent_index':None,'option_group':'','original_text':'모듈 2개 240원'}
    item.update(values)
    return item


def archived(label,price=100):
    content=('invented quotation '+label).encode()
    digest=hashlib.sha256(content).hexdigest()
    path=Path(TEMP.name)/'files'/f'{digest}.pdf';path.write_bytes(content)
    q=d.empty_quote({'source_name':label+'.pdf','source_url':'/api/files/'+path.name,'customer':'가상 고객',
                     'issue_date':'2025-01-01' if label=='past' else '2026-01-01','currency':'KRW',
                     'tax_note':'VAT 별도','items':[row(unit_price=price,amount=price*2)]})
    d.save(q,digest=digest)
    return d.get_quote(q['id']),path


class SubmissionTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        d.engine.dispose();TEMP.cleanup()

    def test_types_relationships_amount_diagnosis_and_read_only(self):
        past,past_path=archived('past')
        current,current_path=archived('current')
        before=copy.deepcopy(d.get_quote(current['id']))
        before_file=current_path.read_bytes()
        types=[('일반 품목 견적',[row(amount=250)]),
               ('대체 옵션 견적',[row(option_group='A'),row('대체형',option_group='A')]),
               ('패키지·구성품 견적',[row('패키지'),row('내부 모듈',is_component=True,parent_index=0)]),
               ('옵션·패키지 혼합 견적',[row('패키지',option_group='A'),row('내부 모듈',is_component=True,parent_index=0,option_group='A')]),
               ('판단 보류',[row()])]
        for doc_type,items in types:
            calls=[]
            def fake(paths,settings):
                calls.append((paths,settings.agent_id))
                if len(calls)==1:return ({'document_type':doc_type,'classification_reason':'가상 원문 표시',
                                           'customer':'가상 고객','issue_date':'2026-01-01','currency':'KRW','tax_note':'VAT 별도',
                                           'items_json':json.dumps(items,ensure_ascii=False),
                                           'item_evidence_json':json.dumps([{'item_index':0,'page':1,'excerpt':'가상 품목'}],ensure_ascii=False)},
                                          {'response_id':'mock_extract','provider':'mock'})
                if len(calls)==2:
                    self.assertEqual(len(paths),2)
                    self.assertEqual(paths[0],current_path)
                    return ({'summary':'가상 문서 확인','review_level':'확인 필요','issues':[{'severity':'높음','what':'원본 금액 확인','why':'수량 × 단가 차이','observed':'240','source':'가상 1쪽','action':'원본 확인'}]}, {'response_id':'mock_review'})
                return ({'summary':'가상 비교 제안','comparison_level':'조건 확인 필요','item_matches':[{'current_row':1,'other_row':1,'status':'조건 확인 필요','reason':'규격 확인'}]}, {'response_id':'mock_compare'})
            record=start([current,past],AGENTS)
            run(record['id'],[current,past],'FAKE_ONLY_IN_MEMORY',runner=fake)
            saved=get(record['id'])
            self.assertEqual(len(calls),3)
            self.assertEqual(saved['stages']['classify']['result']['document_type'],doc_type)
            self.assertEqual(saved['stages']['extract']['result']['evidence'][0]['location']['page'],'1')
            self.assertEqual(saved['stages']['review']['status'],'completed')
            self.assertEqual(saved['stages']['compare']['metadata']['response_id'],'mock_compare')
            self.assertEqual(saved['quote_versions'][current['id']],before['version'])
            self.assertNotIn('FAKE_ONLY_IN_MEMORY',json.dumps(saved))
            self.assertEqual(d.get_quote(current['id']),before)
            self.assertEqual(current_path.read_bytes(),before_file)
            if doc_type=='일반 품목 견적':
                self.assertTrue(any('원본 금액이 수량 × 단가와 다릅니다' in warning for warning in saved['stages']['extract']['calculation_warnings']))
                comparison=saved['stages']['compare']['code_comparison'][0]
                self.assertEqual((comparison['rows'][0]['status'],comparison['rows'][0]['delta'],comparison['rows'][0]['percent']),('comparable',20,20))
            if doc_type=='대체 옵션 견적':
                self.assertIsNone(normalized_extraction(current,{'items':items})['computed_subtotal'])
            if doc_type=='패키지·구성품 견적':
                self.assertEqual(normalized_extraction(current,{'items':items})['computed_subtotal'],240)
        self.assertEqual(past_path.read_bytes(),b'invented quotation past')

    def test_api_requires_user_key_and_consent(self):
        quote,_=archived('no-api')
        request=Request({'type':'http','scheme':'https','path':'/api/analysis-flows',
                         'server':('testserver',443),'headers':[(b'host',b'testserver')]})
        with self.assertRaises(AgentError) as error:
            start_analysis_flow(request,BackgroundTasks(),{'quote_ids':[quote['id']],'agents':AGENTS})
        self.assertIn('API 설정',str(error.exception))
        self.assertEqual(d.get_quote(quote['id'])['source_name'],'no-api.pdf')
        unsafe={role:{**config,'api_key':'FAKE_DO_NOT_SAVE'} for role,config in AGENTS.items()}
        record=start([quote],unsafe)
        self.assertNotIn('FAKE_DO_NOT_SAVE',json.dumps(get(record['id'])))

    def test_failed_review_keeps_extraction_and_code_comparison(self):
        current,_=archived('failure')
        past,_=archived('failure-past')
        def fake(paths,settings):
            if settings.agent_id.endswith('extract'):
                return {'document_type':'일반 품목 견적','items':[row()],'currency':'KRW','tax_note':'VAT 별도'}, {'response_id':'extract_ok'}
            if settings.agent_id.endswith('review'):raise AgentError('가상 검토 오류')
            return {'summary':'비교','item_matches':[]}, {'response_id':'compare_ok'}
        record=start([current,past],AGENTS)
        run(record['id'],[current,past],'FAKE_TOKEN',runner=fake)
        saved=get(record['id'])
        self.assertEqual(saved['status'],'partial')
        self.assertEqual(saved['stages']['review']['status'],'failed')
        self.assertEqual(saved['stages']['extract']['status'],'completed')
        self.assertTrue(saved['stages']['compare']['code_comparison'])

    def test_invalid_output_is_not_applied(self):
        source={'id':'fake','version':1,'source_name':'fake.pdf','source_url':''}
        for result in ({'items':[{'name':'x','unrecognized':'bad'}]},
                       {'items':[row(is_component=True,parent_index=4)]},
                       {'items_json':'invalid'}):
            with self.assertRaises(AgentError):normalized_extraction(source,result)
        with self.assertRaises(AgentError):checked_evidence({'item_evidence_json':'[{"item_index":99}]'},1)

    def test_live_observed_studio_shape_keeps_missing_amount_blank(self):
        source={'id':'fake','version':1,'source_name':'option.pdf','source_url':''}
        extracted=normalized_extraction(source,{'currency':'KRW','tax_note':'VAT 별도','source_total':'',
            'items_json':json.dumps([row('저장 장치',unit_price='100,000 KRW',amount='100,000 KRW',
                option_group='한 가지만 선택',option_choice='A',option_condition='발주자가 선택')],ensure_ascii=False)})
        self.assertEqual(extracted['items'][0]['unit_price'],100000)
        self.assertEqual(extracted['items'][0]['option_choice'],'A')
        self.assertIsNone(extracted['source_total'])
        self.assertIsNone(extracted['computed_subtotal'])
        with self.assertRaises(AgentError):normalized_extraction(source,{'currency':'USD','items':[row(unit_price='100,000 KRW')]})


if __name__=='__main__':unittest.main()
