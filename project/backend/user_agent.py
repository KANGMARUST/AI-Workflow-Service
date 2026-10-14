"""Request-scoped Upstage credentials. Never read a developer/shared API key."""
from dataclasses import dataclass,field
import json,re,time
from urllib.parse import quote
import httpx

GUIDE_URL='https://ku-sejong-hackathon-playbook.vercel.app/'
API_URL='https://api.upstage.ai/v2'


@dataclass(frozen=True)
class AgentSettings:
    api_key:str=field(repr=False)
    agent_id:str
    config_id:str='1'


class AgentError(ValueError):pass


def settings_from_request(request):
    key=request.headers.get('x-user-api-key','').strip()
    agent=request.headers.get('x-user-agent-id','').strip()
    consent=request.headers.get('x-user-ai-consent','')=='yes'
    if not any((key,agent,consent)):return None
    if request.url.scheme!='https' and request.url.hostname not in ('127.0.0.1','localhost','::1','testserver'):
        raise AgentError('외부 배포 환경의 API 설정은 HTTPS 연결에서만 사용할 수 있습니다.')
    if not consent:raise AgentError('외부 에이전트 분석에 동의한 후 API 설정을 적용해주세요.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,512}',key):raise AgentError('API Key를 확인해주세요.')
    if not re.fullmatch(r'agt_[A-Za-z0-9_-]{4,160}',agent):raise AgentError('가이드북에서 Agent ID를 확인해주세요.')
    config=request.headers.get('x-user-config-id','1').strip()
    if not re.fullmatch(r'[1-9][0-9]{0,8}',config):raise AgentError('Config ID는 1 이상의 번호로 입력해주세요.')
    return AgentSettings(key,agent,config)


def safe_id(raw):
    if not isinstance(raw,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',raw):raise AgentError('에이전트 응답의 식별 정보를 확인하지 못했습니다.')
    return quote(raw,safe='')


def scrub(value,secret):
    if isinstance(value,str):return value.replace(secret,'[비밀정보 제거]')
    if isinstance(value,list):return [scrub(item,secret) for item in value]
    if isinstance(value,dict):return {scrub(str(key),secret):scrub(val,secret) for key,val in value.items() if str(key).casefold() not in ('api_key','apikey','authorization','access_token')}
    return value


def run_agent(path,settings,transport=None,timeout=120):
    file_id=None
    try:
        with httpx.Client(base_url=API_URL,headers={'Authorization':'Bearer '+settings.api_key},timeout=30,follow_redirects=False,transport=transport) as client:
            try:
                with path.open('rb') as file:
                    uploaded=client.post('/files',data={'purpose':'user_data'},files={'file':('quotation.pdf',file,'application/pdf')})
                uploaded.raise_for_status();file_id=safe_id(uploaded.json().get('id'))
                response=client.post('/responses',json={'model':settings.agent_id,'include':['last'],'input':[{'role':'user','content':[{'type':'input_file','file_id':file_id}]}],'config_id':settings.config_id})
                response.raise_for_status();job=response.json();job_id=safe_id(job.get('id'))
                deadline=time.monotonic()+timeout
                while job.get('status') in (None,'queued','in_progress'):
                    if time.monotonic()>deadline:raise AgentError('에이전트 분석 시간이 초과되었습니다. 가이드북의 문제 해결을 확인해주세요.')
                    if job.get('status') in ('queued','in_progress'):time.sleep(2)
                    # The Agents API defaults to the final step when include is omitted.
                    response=client.get('/responses/'+job_id);response.raise_for_status();job=response.json()
                if job.get('status')!='completed':raise AgentError('에이전트 실행에 실패했습니다. Agent ID·Config ID와 Studio 실행 결과를 확인해주세요.')
                text=job.get('output_text')
                if not text:
                    text='\n'.join(c.get('text','') for out in job.get('output',[]) if isinstance(out,dict) for c in out.get('content',[]) if isinstance(c,dict) and c.get('type')=='output_text')
                if not isinstance(text,str):raise AgentError('에이전트의 JSON 출력 설정을 확인해주세요.')
                parsed=json.loads(text)
                if not isinstance(parsed,dict):raise AgentError('견적 추출 에이전트의 출력은 JSON 객체여야 합니다.')
                return scrub(parsed,settings.api_key),scrub(dict(provider='upstage',agent_id=settings.agent_id,config_id=settings.config_id,response_id=job_id),settings.api_key)
            finally:
                if file_id:
                    try:client.delete('/files/'+file_id)
                    except httpx.HTTPError:pass
    except httpx.HTTPStatusError as error:
        status=error.response.status_code
        message={401:'API Key 인증에 실패했습니다.',403:'이 API Key의 에이전트 접근 권한을 확인해주세요.',404:'Agent ID·Config ID를 확인해주세요.',429:'API 사용량 또는 호출 한도를 확인해주세요.'}.get(status,'외부 에이전트 요청에 실패했습니다. 가이드북의 문제 해결을 확인해주세요.')
        raise AgentError(message) from None
    except (httpx.HTTPError,json.JSONDecodeError,TypeError,AttributeError):
        raise AgentError('외부 에이전트 연결 또는 JSON 응답을 확인하지 못했습니다.') from None


def merge_agent_result(q,result):
    if 'items_json' in result and 'items' not in result:
        raw=result['items_json']
        if isinstance(raw,list) and len(raw)==1:raw=raw[0]
        try:result={**result,'items':json.loads(raw)}
        except (TypeError,json.JSONDecodeError):raise AgentError('에이전트 items_json은 품목 JSON 배열이어야 합니다.') from None
    allowed=('number','customer','issuer','issue_date','valid_until','delivery','ship_to','payment_terms','project_name','currency','tax_note','tax_rate','subtotal','tax','total','source_total','source_total_kind','notes','items')
    recognized=False
    for key in allowed:
        if key not in result:continue
        val=result[key]
        if key!='items' and isinstance(val,list):val=val[0] if len(val)==1 else None
        if val is None or val=='':continue
        if key=='items':
            if not isinstance(val,list) or any(not isinstance(item,dict) for item in val):raise AgentError('에이전트 출력의 items 스키마를 확인해주세요.')
            item_keys=('name','specification','unit','quantity','unit_price','amount','is_component','parent_index','option_group','original_text')
            q[key]=[{k:v for k,v in item.items() if k in item_keys} for item in val]
        elif isinstance(val,(str,int,float)):q[key]=val
        else:raise AgentError('에이전트 출력의 견적 필드 스키마를 확인해주세요.')
        recognized=True
    if not recognized:raise AgentError('견적 추출 에이전트의 출력 항목명을 개발 명세와 맞춰주세요.')
