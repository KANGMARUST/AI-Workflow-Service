from __future__ import annotations
import os,uuid,json,re,hashlib,importlib.util
from pathlib import Path
from datetime import date
from collections import defaultdict
from fastapi import FastAPI,HTTPException,UploadFile,File,Body
from fastapi.responses import FileResponse,JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
import domain as d
import extraction

app=FastAPI(title='견적 아카이브 AI',version='2.0.0')
app.add_middleware(CORSMiddleware,allow_origins=(os.getenv('CORS_ORIGINS') or 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173').split(','),allow_methods=['*'],allow_headers=['*'])
MAX_SIZE=30*1024*1024
d.migrate_archive()
@app.exception_handler(ValueError)
async def value_error(request,exc):return JSONResponse(status_code=422,content={'detail':str(exc)})
def require(id):
    q=d.get_quote(id)
    if not q:raise HTTPException(404,'원본 파일이 연결된 아카이브 견적서를 찾지 못했습니다.')
    return q
def version_save(q,previous):
    q['version']=previous['version']+1;q['id']=previous['id'];q['created_at']=previous['created_at']
    return d.save(d.calculate(q),previous=previous)
def ingest(path,name):
    digest=hashlib.sha256(path.read_bytes()).hexdigest();existing=d.duplicate(digest)
    if existing:
        result=dict(existing);result['warnings']=existing['warnings']+['중복 파일입니다. 기존 아카이브 문서를 불러왔습니다.'];return result
    quote=extraction.extract(path);filename=digest+path.suffix.lower();destination=d.STORAGE/'files'/filename
    if path!=destination:destination.write_bytes(path.read_bytes())
    quote.update(source_name=name,source_url='/api/files/'+filename)
    return d.save(quote,digest=digest)
@app.get('/api/health')
def health():return dict(ok=True,mode='archive',extraction_mode='external-ai opt-in + local' if os.getenv('EXTERNAL_AI_ENABLED','false').lower()=='true' and os.getenv('OPENAI_API_KEY') else 'local-parser + local-ocr',ocr_available=importlib.util.find_spec('rapidocr_onnxruntime') is not None,database='postgresql' if d.url.startswith('postgres') else 'sqlite')
@app.get('/api/quotes')
def quotes(query:str='',customer:str='',contact:str='',phone:str='',title:str='',number:str='',item:str='',date_from:str='',date_to:str='',min_amount:float|None=None,max_amount:float|None=None,review_status:str=''):return d.filtered(locals())
@app.get('/api/quotes/{id}')
def get(id:str):return require(id)
@app.put('/api/quotes/{id}')
def update(id:str,payload:dict=Body(...)):
    previous=require(id);q=json.loads(json.dumps(previous))
    allowed={'number','customer','issuer','contact','customer_contact','phone','email','issue_date','valid_until','delivery','ship_to','payment_terms','project_name','currency','tax_note','tax_rate','subtotal','tax','total','source_total','source_total_kind','notes','items','acknowledged_warnings'}
    q.update({k:v for k,v in payload.items() if k in allowed});q['review_status']='pending';q['acknowledged_warnings']=bool(payload.get('acknowledged_warnings',False))
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
async def upload(files:list[UploadFile]=File(...)):
    result=[];errors=[]
    for file in files:
        temp=None
        try:
            extension=Path(file.filename or '').suffix.lower()
            if extension not in ('.xls','.xlsx','.pdf','.docx','.png','.jpg','.jpeg'):raise ValueError('지원하지 않는 파일 형식입니다.')
            content=await file.read(MAX_SIZE+1)
            if len(content)>MAX_SIZE:raise ValueError('파일당 최대 30MB까지 업로드할 수 있습니다.')
            if not content:raise ValueError('빈 파일입니다.')
            temp=d.STORAGE/'files'/('upload-'+uuid.uuid4().hex+extension);temp.write_bytes(content);result.append(ingest(temp,Path(file.filename).name))
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
@app.post('/api/natural-search')
def natural(payload:dict=Body(...)):
    question=str(payload.get('question','')).strip()
    if not question:raise HTTPException(422,'검색할 질문을 입력해주세요.')
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
