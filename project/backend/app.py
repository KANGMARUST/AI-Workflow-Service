from __future__ import annotations
import os,uuid,json,re,hashlib,importlib.util
from pathlib import Path
from datetime import date
from collections import defaultdict
from fastapi import FastAPI,HTTPException,UploadFile,File,Body,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
import domain as d
import extraction

app=FastAPI(title='견적 아카이브 AI',version='2.0.0')
app.add_middleware(CORSMiddleware,allow_origins=(os.getenv('CORS_ORIGINS') or 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173').split(','),allow_methods=['*'],allow_headers=['*'])
MAX_SIZE=30*1024*1024
d.migrate_archive()
d.backfill_document_content()
d.backfill_details()
d.backfill_people()
@app.exception_handler(ValueError)
async def value_error(request,exc):return JSONResponse(status_code=422,content={'detail':str(exc)})
def require(id):
    q=d.get_quote(id)
    if not q:raise HTTPException(404,'원본 파일이 연결된 아카이브 견적서를 찾지 못했습니다.')
    return q

@app.get('/api/agent-runs')
def agent_runs():
    from agent_workflow import list_runs
    return list_runs()

@app.post('/api/agent-runs')
def agent_run(request:Request,payload:dict=Body(...)):
    from user_agent import settings_from_request,AgentError
    from agent_workflow import execute
    settings=settings_from_request(request)
    if settings is None:raise AgentError('API 설정에서 본인 API와 해당 역할의 에이전트를 적용해주세요.')
    ids=payload.get('quote_ids')
    if not isinstance(ids,list) or any(not isinstance(i,str) for i in ids) or len(ids)>5 or len(set(ids))!=len(ids):raise AgentError('중복 없이 문서 1~5개를 선택해주세요.')
    return execute(payload.get('kind'),[require(i) for i in ids],settings)
def version_save(q,previous):
    q['version']=previous['version']+1;q['id']=previous['id'];q['created_at']=previous['created_at']
    return d.save(d.calculate(q),previous=previous)
def ingest(path,name,agent_settings=None):
    digest=hashlib.sha256(path.read_bytes()).hexdigest();existing=d.duplicate(digest)
    if existing:
        if existing.get('deleted_at'):raise ValueError('휴지통에 같은 파일이 있습니다. 휴지통에서 해당 견적서를 복원해주세요.')
        result=dict(existing);result['warnings']=existing['warnings']+['중복 파일입니다. 기존 아카이브 문서를 불러왔습니다.'];return result
    quote=extraction.extract(path,agent_settings=agent_settings);filename=digest+path.suffix.lower();destination=d.STORAGE/'files'/filename
    if path!=destination:destination.write_bytes(path.read_bytes())
    quote.update(source_name=name,source_url='/api/files/'+filename)
    return d.save(quote,digest=digest)
@app.get('/api/health')
def health():return dict(ok=True,mode='archive',extraction_mode='local-parser + local-ocr; user-upstage-agent opt-in',shared_api_key=False,ocr_available=importlib.util.find_spec('rapidocr_onnxruntime') is not None,database='postgresql' if d.url.startswith('postgres') else 'sqlite')
@app.get('/api/quotes')
def quotes(query:str='',customer:str='',contact:str='',phone:str='',title:str='',number:str='',item:str='',date_from:str='',date_to:str='',min_amount:float|None=None,max_amount:float|None=None,review_status:str=''):return d.filtered(locals())
@app.get('/api/quotes/{id}')
def get(id:str):return require(id)
@app.put('/api/quotes/{id}')
def update(id:str,payload:dict=Body(...)):
    previous=require(id);q=json.loads(json.dumps(previous))
    allowed={'number','customer','issuer','contact','customer_contact','phone','email','issue_date','valid_until','delivery','ship_to','payment_terms','project_name','currency','tax_note','tax_rate','subtotal','tax','total','source_total','source_total_kind','notes','items','acknowledged_warnings','extra_fields'}
    if 'extra_fields' in payload:
        fields=payload['extra_fields']
        if not isinstance(fields,list) or any(not isinstance(field,dict) or not isinstance(field.get('label'),str) or not isinstance(field.get('value'),str) for field in fields):raise ValueError('추가 정보는 항목명과 내용으로 입력해주세요.')
    if 'detailed_fields' in payload:
        fields=payload['detailed_fields']
        original={field['id']:field for field in previous.get('detailed_fields',[])}
        if not isinstance(fields,list) or len(fields)!=len(original) or any(not isinstance(field,dict) or field.get('id') not in original or not isinstance(field.get('value'),str) for field in fields) or len({field['id'] for field in fields})!=len(original):raise ValueError('세부 정보의 내용을 원본과 대조해 정정해주세요.')
        q['detailed_fields']=[{**original[field['id']],'value':field['value'],'origin':'corrected' if field['value']!=original[field['id']]['value'] else original[field['id']].get('origin','source')} for field in fields]
    if 'people_records' in payload:
        from people_capture import FIELDS,blank
        people=payload['people_records']
        if not isinstance(people,list) or any(not isinstance(p,dict) or any(not isinstance(p.get(field,''),str) for field in FIELDS) for p in people):raise ValueError('인적 사항은 이름·연락처 등 항목별 텍스트로 입력해주세요.')
        originals={p['id']:p for p in previous.get('people_records',[])};saved=[];seen=set()
        for person in people:
            ident=person.get('id')
            if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{24,32}',ident) or ident in seen:raise ValueError('인적 사항 식별 정보를 확인해주세요.')
            seen.add(ident);entry=json.loads(json.dumps(originals.get(ident) or blank()))
            entry.update(id=ident,**{field:person.get(field,'') for field in FIELDS})
            entry['review_status']='confirmed' if person.get('review_status')=='confirmed' else 'pending'
            if ident not in originals:entry.update(origin='manual',source_records=[])
            elif any(entry[field]!=originals[ident].get(field,'') for field in FIELDS):entry['origin']='corrected'
            saved.append(entry)
        q['people_records']=saved
    q.update({k:v for k,v in payload.items() if k in allowed});q['review_status']='pending';q['acknowledged_warnings']=bool(payload.get('acknowledged_warnings',False))
    from quote_details import extract_details
    q['item_specifications']=extract_details(q)['item_specifications']
    return version_save(q,previous)
@app.delete('/api/quotes/{id}')
def trash(id:str):
    previous=require(id);q=json.loads(json.dumps(previous));q['deleted_at']=d.now()
    return version_save(q,previous)
@app.get('/api/trash')
def trash_list():return d.trashed_quotes()
@app.post('/api/quotes/{id}/restore')
def restore(id:str):
    previous=d.get_quote(id,include_deleted=True)
    if not previous:raise HTTPException(404,'복원할 견적서를 찾지 못했습니다.')
    if not previous.get('deleted_at'):return previous
    q=json.loads(json.dumps(previous));q.pop('deleted_at',None)
    return version_save(q,previous)
@app.post('/api/quotes/{id}/confirm')
def confirm(id:str,payload:dict|None=Body(default=None)):
    previous=require(id);q=d.calculate(json.loads(json.dumps(previous)))
    if payload and 'acknowledged_warnings' in payload:q['acknowledged_warnings']=bool(payload['acknowledged_warnings'])
    if q['warnings'] and not q.get('acknowledged_warnings'):raise HTTPException(422,'원본의 미기재·불일치·선택 조건을 검토한 후 확인해주세요.')
    q['review_status']='confirmed';return version_save(q,previous)
@app.get('/api/quotes/{id}/history')
def history(id:str):
    require(id)
    with d.engine.connect() as c:rows=c.execute(select(d.history_table).where(d.history_table.c.quote_id==id).order_by(d.history_table.c.version.desc())).all()
    result=[]
    for row in rows:
        snapshot=json.loads(row.snapshot);snapshot['source_text']=extraction.sanitize_pdf(snapshot.get('source_text',''))
        result.append(dict(version=row.version,changed_at=row.changed_at,snapshot=snapshot))
    return result
@app.post('/api/upload')
async def upload(request:Request,files:list[UploadFile]=File(...)):
    from user_agent import settings_from_request
    agent_settings=settings_from_request(request)
    result=[];errors=[]
    for file in files:
        temp=None
        try:
            extension=Path(file.filename or '').suffix.lower()
            if extension not in ('.xls','.xlsx','.pdf','.docx','.png','.jpg','.jpeg'):raise ValueError('지원하지 않는 파일 형식입니다.')
            content=await file.read(MAX_SIZE+1)
            if len(content)>MAX_SIZE:raise ValueError('파일당 최대 30MB까지 업로드할 수 있습니다.')
            if not content:raise ValueError('빈 파일입니다.')
            temp=d.STORAGE/'files'/('upload-'+uuid.uuid4().hex+extension);temp.write_bytes(content);result.append(ingest(temp,Path(file.filename).name,agent_settings))
        except Exception as exc:errors.append({'filename':file.filename,'detail':str(exc)[:400]})
        finally:
            if temp and temp.exists():temp.unlink()
            await file.close()
    return dict(quotes=result,errors=errors)
@app.post('/api/import-samples')
def samples():
    result=[];errors=[]
    if not d.SAMPLES.exists():return dict(quotes=[],errors=[dict(filename='data',detail='샘플 폴더를 찾지 못했습니다.')])
    for f in sorted(d.SAMPLES.iterdir()):
        if f.suffix.lower() not in ('.pdf','.xls','.xlsx','.docx','.png','.jpg','.jpeg'):continue
        try:result.append(ingest(f,f.name))
        except Exception as exc:errors.append(dict(filename=f.name,detail=str(exc)[:400]))
    return dict(quotes=result,errors=errors)
@app.get('/api/compare')
def compare(query:str='',include_pending:bool=True):
    result=[]
    for q in d.all_quotes():
        if not include_pending and q['review_status']!='confirmed':continue
        for it in q['items']:
            if query.casefold() not in (it['name']+' '+it['specification']).casefold():continue
            result.append({k:q.get(k) for k in ('number','customer','contact','customer_contact','phone','project_name','issue_date','currency','delivery','payment_terms','review_status')}|dict(quote_id=q['id'])|{k:it.get(k) for k in ('name','specification','unit','quantity','unit_price','amount','is_component','parent_index','option_group')})
    return sorted(result,key=lambda row:row['issue_date'],reverse=True)
@app.get('/api/categories')
def categories():
    from category_view import browse
    return browse(d.all_quotes())[0]
@app.get('/api/categories/{key:path}')
def category_values(key:str,query:str=''):
    from category_view import browse
    categories,rows=browse(d.all_quotes())
    category=next((c for c in categories if c['key']==key),None)
    if category is None:raise HTTPException(404,'조회할 카테고리를 찾지 못했습니다.')
    values=rows[key]
    if query.strip():
        needle=query.strip().casefold()
        values=[row for row in values if needle in ' '.join(str(row.get(field) or '') for field in ('value','person_name','person_role','customer','quote_title','source_name')).casefold() or (key in ('fax','phone','mobile') and needle.isdigit() and needle in re.sub(r'\D','',row['value']))]
    return dict(category=category,values=values,count=len(values))
@app.post('/api/natural-search')
def natural(request:Request,payload:dict=Body(...)):
    question=str(payload.get('question','')).strip()
    if not question:raise HTTPException(422,'검색할 질문을 입력해주세요.')
    if len(question)>1000:raise HTTPException(422,'질문은 1000자 이내로 입력해주세요.')
    from user_agent import settings_from_request
    settings=settings_from_request(request)
    if settings:
        from natural_answer import CHAT_MODELS, MODEL, answer_with_api
        model=payload.get('model',MODEL)
        if not isinstance(model,str) or model not in CHAT_MODELS:
            raise HTTPException(422,'지원하지 않는 Solar Chat 모델입니다.')
        history=payload.get('history',[])
        if not isinstance(history,list) or len(history)>12 or any(
            not isinstance(turn,dict) or turn.get('role') not in ('user','assistant') or
            not isinstance(turn.get('content'),str) or len(turn['content'])>2000
            for turn in history):
            raise HTTPException(422,'이전 대화 형식을 확인해주세요.')
        return answer_with_api(question,d.all_quotes(),settings.api_key,history=history[-8:],model=model)
    filters={}
    stopwords={'견적','견적서','건','품목','품목명','프로젝트','제목','담당자','내역','조회','검색','전체'}
    if re.search(r'검토\s*필요|미확정|검토\s*대기',question):filters['review_status']='pending'
    elif re.search(r'확정|검토완료',question):filters['review_status']='confirmed'
    dates=re.findall(r'20\d{2}-\d{2}-\d{2}',question)
    if dates:
        filters['date_from']=dates[0]
        if len(dates)>1:filters['date_to']=dates[1]
        elif '이전' in question:filters['date_to']=dates[0];filters.pop('date_from')
    else:
        month=re.search(r'(20\d{2})\s*년?\s*(\d{1,2})\s*월',question);year=re.search(r'(20\d{2})\s*년',question)
        import calendar
        if month:
            y,m=map(int,month.groups())
            if 1<=m<=12:filters.update(date_from=f'{y}-{m:02}-01',date_to=f'{y}-{m:02}-{calendar.monthrange(y,m)[1]}')
        elif year:filters.update(date_from=year.group(1)+'-01-01',date_to=year.group(1)+'-12-31')
        elif '이번 달' in question:
            today=date.today();filters.update(date_from=today.replace(day=1).isoformat(),date_to=today.isoformat())
    for match in re.finditer(r'([\d,.]+)\s*(억|만|천)?\s*원?\s*(이상|이하|초과|미만)',question):
        value=float(match.group(1).replace(',',''))*{'억':100000000,'만':10000,'천':1000,None:1}[match.group(2)]
        filters['min_amount' if match.group(3) in ('이상','초과') else 'max_amount']=value
    stored=d.all_quotes()
    for field in ('customer','contact','phone','project_name','number'):
        values=sorted(set(q.get(field,'') or '' for q in stored),key=len,reverse=True)
        if field=='contact':values+=list(set(q.get('customer_contact','') or '' for q in stored))
        for value in values:
            clean=re.sub(r'㈜|주식회사|\(주\)|\s','',value)
            if value and (value.casefold() in question.casefold() or (clean and clean.casefold() in question.casefold())):filters['title' if field=='project_name' else field]=value;break
    phone=re.search(r'0\d{1,2}[- ]?\d{3,4}[- ]?\d{4}',question)
    if phone:filters['phone']=phone.group()
    quoted=re.search(r'["“\']([^"”\']+)["”\']',question)
    if quoted:
        value=quoted.group(1)
        if any(value in q.get('project_name','') for q in stored):filters['title']=value
        else:filters['item']=value
    else:
        tokens=set()
        for q in stored:
            for it in q['items']:
                for token in re.split(r'\s+',it['name']):
                    if len(token)>=2 and token not in stopwords and token.casefold() in question.casefold():tokens.add(token)
        if tokens:filters['item']=max(tokens,key=len)
        title_tokens=[token for q in stored for token in q.get('project_name','').split() if len(token)>=2 and token not in stopwords and token in question]
        if title_tokens and 'title' not in filters:filters['title']=max(title_tokens,key=len)
    if not filters:
        cleaned=re.sub(r'견적서?|찾아줘|찾아|검색해줘|검색|보여줘|보여|알려줘|내역|이력|전체|최근|어떤|있어|있나요|담당자|프로젝트|제목|[?？]',' ',question).strip()
        if cleaned:filters['query']=cleaned
    found=d.filtered(filters)
    return dict(answer=f'저장된 원본 견적에서 {len(found)}건을 찾았습니다. 금액 조건은 원본에 명시된 합계 기준이며 VAT 별도·포함 조건을 함께 확인하세요.',quotes=found,filters=filters,method='local-condition-parser')
@app.get('/api/stats')
def stats():
    quotes=d.all_quotes();confirmed=[q for q in quotes if q['review_status']=='confirmed'];monthly=defaultdict(lambda:dict(count=0,amount=0));customers=defaultdict(lambda:dict(count=0,amount=0))
    known=[]
    for q in quotes:
        month=q['issue_date'][:7] or '미지정';monthly[month]['count']+=1;customers[q['customer']]['count']+=1;amount=d.display_amount(q)
        if q['currency']=='KRW' and amount is not None:
            monthly[month]['amount']+=amount;customers[q['customer']]['amount']+=amount;known.append(amount)
    return dict(quote_count=len(quotes),confirmed_count=len(confirmed),pending_count=len(quotes)-len(confirmed),customer_count=len(set(q['customer'] for q in quotes if q['customer'])),item_count=sum(len(q['items']) for q in quotes),quoted_amount=sum(known),currency='KRW',amount_note='원본 명시 금액 합계(KRW). VAT 포함·별도가 혼재할 수 있으며 미기재 금액은 제외.',monthly=[dict(month=k,**v) for k,v in sorted(monthly.items())],customers=[dict(customer=k,**v) for k,v in sorted(customers.items(),key=lambda pair:pair[1]['count'],reverse=True)])
@app.get('/api/files/{filename}')
def source(filename:str):
    if not re.fullmatch(r'[a-f0-9]{64}\.(pdf|xls|xlsx|docx|png|jpe?g)',filename):raise HTTPException(404,'원본 파일을 찾지 못했습니다.')
    path=(d.STORAGE/'files'/filename).resolve()
    if path.parent!=(d.STORAGE/'files').resolve() or not path.is_file():raise HTTPException(404,'원본 파일을 찾지 못했습니다.')
    return FileResponse(path,filename=filename,content_disposition_type='inline' if path.suffix in ('.pdf','.png','.jpg','.jpeg') else 'attachment')
@app.post('/api/quotes')
@app.post('/api/quotes/{id}/copy')
@app.patch('/api/quotes/{id}/status')
@app.get('/api/quotes/{id}/export')
@app.get('/api/templates')
@app.post('/api/templates')
def removed(id:str=''):
    raise HTTPException(410,'기존 견적서 아카이브 전용 서비스입니다. 새 견적 작성·복사·상태 변경·양식·출력 기능은 제거되었습니다.')
