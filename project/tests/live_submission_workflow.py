"""Authorized live run against invented PDFs and an isolated archive only."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend/.packages'),str(ROOT/'backend'),str(ROOT/'tests')]
RUNS=ROOT/'tests'/'.runs'/'live-submission'
RUNS.mkdir(parents=True,exist_ok=True)
os.environ['QUOTE_DATA_DIR']=str(RUNS)
os.environ['DATABASE_URL']='sqlite:///'+(RUNS/'quotes.db').as_posix()

import domain as d
from live_quote_agents import test_key
from submission_workflow import get,run,start


def fixture_quote(filename,when,price):
    path=ROOT/'tests'/'fixtures'/'hackathon'/filename
    content=path.read_bytes()
    digest=hashlib.sha256(content).hexdigest()
    target=RUNS/'files'/f'{digest}.pdf'
    if not target.exists():target.write_bytes(content)
    q=d.empty_quote({'source_name':filename,'source_url':'/api/files/'+target.name,'issue_date':when,
        'customer':'가상 연구소','currency':'KRW','tax_note':'VAT 별도','delivery':'3주' if price==100000 else '4주',
        'payment_terms':'납품 후 30일','items':[{'name':'광학 모듈','model':'OM-100','specification':'10 mm',
        'unit':'개','quantity':2,'unit_price':price,'amount':price*2,'original_text':'가상 견적 품목 1행'}]})
    d.save(q,digest=digest)
    return d.get_quote(q['id']),content


def main():
    past,past_bytes=fixture_quote('일반_과거.pdf','2025-01-10',100000)
    current,current_bytes=fixture_quote('일반_현재.pdf','2026-01-10',120000)
    before={q['id']:json.dumps(d.get_quote(q['id']),ensure_ascii=False,sort_keys=True) for q in (past,current)}
    agents={'extract':{'agent_id':'agt_WUmdoTPSummj3uQ7Qdi6dM','config_id':'3'},
            'review':{'agent_id':'agt_3meY3NJetTYi7X9n8RTPpB','config_id':'2'},
            'compare':{'agent_id':'agt_R5gPHUeVuUoDCheCftTnDL','config_id':'2'}}
    record=start([current,past],agents)
    began=time.monotonic()
    run(record['id'],[current,past],test_key())
    saved=get(record['id'])
    preserved=all(json.dumps(d.get_quote(q['id']),ensure_ascii=False,sort_keys=True)==before[q['id']] for q in (past,current))
    preserved=preserved and (RUNS/'files'/Path(past['source_url']).name).read_bytes()==past_bytes and (RUNS/'files'/Path(current['source_url']).name).read_bytes()==current_bytes
    attempted=sum(saved['stages'][key]['status'] in ('completed','failed') for key in ('extract','review','compare'))
    completed=sum(saved['stages'][key]['status']=='completed' for key in ('extract','review','compare'))
    result={'live_api_called':attempted>0 and ('API Key 인증에 실패했습니다.' in saved['stages']['extract'].get('error','') or completed>0),
            'input_documents':2,'api_steps_planned':3,'api_steps_attempted':attempted,'api_steps_completed':completed,
            'elapsed_seconds':round(time.monotonic()-began,2),
            'record_id':record['id'],'status':saved['status'],'originals_and_quotes_preserved':preserved,
            'stages':{key:{'status':value['status'],'elapsed_seconds':value.get('elapsed_seconds'),
                           'response_id':value.get('metadata',{}).get('response_id'),'error':value.get('error'),
                           'document_type':value.get('result',{}).get('document_type') if isinstance(value.get('result'),dict) else None,
                           'fields':list(value.get('result',{})) if isinstance(value.get('result'),dict) else []}
                      for key,value in saved['stages'].items()},
            'code_summary':saved['stages']['compare'].get('code_comparison',[{}])[0].get('summary',{}) if saved['stages']['compare'].get('code_comparison') else {},
            'limitations':('가상 2문서의 추출·검토·비교 API 흐름만 확인. AI 정확도 일반화나 원본 전체 대조를 뜻하지 않음.'
                           if saved['status']=='completed' else '추출 단계 실패. 검토·비교 API는 실행되지 않았고 전체 흐름은 미검증.')}
    out=ROOT/'tests'/'live-submission-results.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    if not preserved or saved['status']!='completed':sys.exit(1)


if __name__=='__main__':main()
