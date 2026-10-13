from __future__ import annotations
import os,json,uuid,re
from pathlib import Path
from datetime import datetime,date
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from sqlalchemy import create_engine,MetaData,Table,Column,String,Text,Integer,select
from dotenv import load_dotenv
BASE=Path(__file__).resolve().parent
load_dotenv(BASE.parent/'.env');load_dotenv(BASE/'.env')
STORAGE=Path(os.getenv('QUOTE_DATA_DIR') or BASE/'storage').resolve()
SAMPLES=Path(os.getenv('QUOTE_SAMPLE_DIR') or BASE.parent/'data').resolve()
for path in (STORAGE,STORAGE/'files'):path.mkdir(parents=True,exist_ok=True)
url=os.getenv('DATABASE_URL') or 'sqlite:///'+(STORAGE/'quotes.db').as_posix()
if url.startswith('postgres://'):url=url.replace('postgres://','postgresql+psycopg://',1)
if url.startswith('postgresql://'):url=url.replace('postgresql://','postgresql+psycopg://',1)
engine=create_engine(url,connect_args={'check_same_thread':False} if url.startswith('sqlite') else {},pool_pre_ping=True)
meta=MetaData()
quotes_table=Table('quotes',meta,Column('id',String(36),primary_key=True),Column('payload',Text,nullable=False),Column('file_hash',String(64),index=True))
history_table=Table('quote_history',meta,Column('id',String(36),primary_key=True),Column('quote_id',String(36),index=True),Column('version',Integer),Column('changed_at',String(40)),Column('snapshot',Text))
meta.create_all(engine)
def now():return datetime.now().astimezone().isoformat()
def decimal(v):
    if v is None or v=='':return None
    try:
        result=Decimal(str(v).replace(',','').replace('₩','').strip())
        if not result.is_finite():raise ValueError('유한한 숫자만 입력할 수 있습니다.')
        return result
    except (InvalidOperation,ValueError):raise ValueError('숫자 형식을 확인해주세요: '+str(v))
def n(v):
    if v is None:return None
    return int(v) if v==v.to_integral_value() else float(v)
def empty_quote(data=None):
    q=dict(id=str(uuid.uuid4()),number='',customer='',issuer='',contact='',customer_contact='',phone='',email='',issue_date='',valid_until='',delivery='',ship_to='',payment_terms='',project_name='',currency='KRW',tax_note='원본 미기재',tax_rate=None,subtotal=None,tax=None,total=None,source_total=None,source_total_kind='unknown',review_status='pending',notes='',items=[],warnings=[],source_url='',source_name='',source_text='',extraction_method='manual',version=1,created_at=now(),updated_at=now(),acknowledged_warnings=False,extraction_warnings=[],archive_schema_version=2)
    if data:q.update(data)
    return calculate(q)
def calculate(q):
    warnings=[]
    if not q.get('customer'):warnings.append('거래처가 원본에서 확인되지 않았습니다.')
    if not q.get('issue_date'):warnings.append('견적일자가 원본에서 확인되지 않았습니다.')
    elif q.get('issue_date'):
        try:date.fromisoformat(q['issue_date'])
        except (ValueError,TypeError):warnings.append('견적일자는 YYYY-MM-DD 형식으로 확인해주세요.')
    items=q.get('items') or []
    if not isinstance(items,list) or any(not isinstance(it,dict) for it in items):raise ValueError('품목은 항목 객체의 배열이어야 합니다.')
    if not items:warnings.append('원본 품목을 확인하지 못했습니다. 원본을 보고 보완해주세요.')
    computed=Decimal(0);complete=True
    scale=Decimal('1') if q.get('currency') in ('KRW','JPY') else Decimal('.01')
    for i,it in enumerate(items):
        it.pop('included',None)
        for key,default in [('name',''),('specification',''),('unit',''),('is_component',False),('parent_index',None),('option_group',''),('original_text','')]:it.setdefault(key,default)
        if not it['name']:warnings.append(f'{i+1}행 품목명이 확인되지 않았습니다.')
        values={key:decimal(it.get(key)) for key in ('quantity','unit_price','amount')}
        for key,label in [('quantity','수량'),('unit_price','단가'),('amount','금액')]:
            value=values[key];it[key]=n(value)
            if value is None:warnings.append(f'{i+1}행 {label}가 원본에서 확인되지 않았습니다.')
            elif value<0:warnings.append(f'{i+1}행 {label}가 음수입니다. 원본을 확인해주세요.')
        product=(values['quantity']*values['unit_price']).quantize(scale,rounding=ROUND_HALF_UP) if values['quantity'] is not None and values['unit_price'] is not None else None
        it['computed_amount']=n(product)
        if values['amount'] is not None and product is not None and abs(values['amount']-product)>scale/2:warnings.append(f'{i+1}행 원본 금액이 수량 × 단가와 다릅니다. 원본 값을 보존했습니다.')
        if it['is_component']:
            parent=it['parent_index']
            if not isinstance(parent,int) or parent<0 or parent>=len(items) or parent==i or items[parent].get('is_component'):warnings.append(f'{i+1}행 부품의 상위 패키지 연결을 확인해주세요.')
        elif values['amount'] is None:complete=False
        else:computed+=values['amount']
    if any(it.get('option_group') for it in items):
        complete=False;warnings.append('원본에는 대체 옵션이 있습니다. 모든 옵션을 보존하며 선택·합계를 자동 결정하지 않습니다.')
    q['computed_subtotal']=n(computed) if complete and items else None
    for key in ('subtotal','tax_rate','tax','total','source_total'):q[key]=n(decimal(q.get(key)))
    if q['subtotal'] is not None and q['computed_subtotal'] is not None and abs(decimal(q['subtotal'])-computed)>scale/2:warnings.append('원본 공급가액과 품목 금액 합계가 다릅니다. 원본 값을 보존했습니다.')
    if q['subtotal'] is None and q['total'] is None:warnings.append('원본 합계가 숫자로 명시되지 않았습니다. 미기재·선택 조건을 확인해주세요.')
    if q.get('source_total_kind')=='subtotal' and q['tax_rate'] is None:warnings.append('VAT 별도 원본입니다. 세율·세액·세금 포함 총액은 원본에 없으므로 비워 두었습니다.')
    warnings.extend(q.get('extraction_warnings') or [])
    q['warnings']=list(dict.fromkeys(warnings));q['blocking_warnings']=[]
    q.pop('discount',None);q.pop('tax_inferred',None);q.pop('status',None);q.pop('parent_id',None)
    return q

def is_archive(row):
    if not row.file_hash:return False
    q=json.loads(row.payload)
    if q.get('parent_id'):return False
    filename=Path(q.get('source_url','')).name
    return bool(re.fullmatch(r'[a-f0-9]{64}\.(pdf|xls|xlsx|docx|png|jpe?g)',filename) and Path(filename).stem==row.file_hash and (STORAGE/'files'/filename).is_file())
def all_quotes():
    with engine.connect() as c:return [json.loads(row.payload) for row in c.execute(select(quotes_table)).all() if is_archive(row)]
def get_quote(id):
    with engine.connect() as c:row=c.execute(select(quotes_table).where(quotes_table.c.id==id)).first()
    return json.loads(row.payload) if row and is_archive(row) else None
def duplicate(digest):
    with engine.connect() as c:row=c.execute(select(quotes_table).where(quotes_table.c.file_hash==digest)).first()
    return json.loads(row.payload) if row and is_archive(row) else None
def save(q,digest=None,previous=None):
    q['updated_at']=now()
    with engine.begin() as c:
        if previous:
            c.execute(history_table.insert().values(id=str(uuid.uuid4()),quote_id=q['id'],version=previous['version'],changed_at=q['updated_at'],snapshot=json.dumps(previous,ensure_ascii=False)))
            c.execute(quotes_table.update().where(quotes_table.c.id==q['id']).values(payload=json.dumps(q,ensure_ascii=False)))
        else:c.execute(quotes_table.insert().values(id=q['id'],payload=json.dumps(q,ensure_ascii=False),file_hash=digest))
    return q

def display_amount(q):return q.get('source_total') if q.get('source_total') is not None else q.get('total') if q.get('total') is not None else q.get('subtotal')
def filtered(filters):
    result=all_quotes()
    for key in ('customer','contact','phone','title','query','item','number'):
        value=(filters.get(key) or '').casefold().strip()
        if not value:continue
        def match(q):
            if key=='contact':text=q.get('contact','')+' '+q.get('customer_contact','')
            elif key in ('customer','number'):text=q.get(key,'')
            elif key=='phone':text=q.get('phone','')
            elif key=='title':text=q.get('project_name','')
            elif key=='item':text=' '.join(x.get('name','')+' '+x.get('specification','') for x in q['items'])
            else:
                text=' '.join(str(q.get(field) or '') for field in ('number','customer','contact','customer_contact','phone','email','issuer','project_name','source_name','source_text','notes'))+' '+' '.join(str(it.get(field) or '') for it in q['items'] for field in ('name','specification','unit','original_text'))
            if key=='phone':
                digits=re.sub(r'\D','',value)
                return bool(digits) and digits in re.sub(r'\D','',text)
            return value in text.casefold()
        result=[q for q in result if match(q)]
    if filters.get('review_status'):result=[q for q in result if q['review_status']==filters['review_status']]
    if filters.get('date_from'):result=[q for q in result if q['issue_date'] and q['issue_date']>=filters['date_from']]
    if filters.get('date_to'):result=[q for q in result if q['issue_date'] and q['issue_date']<=filters['date_to']]
    for key,op in [('min_amount',lambda x,y:x>=y),('max_amount',lambda x,y:x<=y)]:
        if filters.get(key) not in (None,''):result=[q for q in result if display_amount(q) is not None and op(decimal(display_amount(q)),decimal(filters[key]))]
    return sorted(result,key=lambda q:q['updated_at'],reverse=True)

def migrate_archive():
    # Preserve legacy rows and corrected fields. Only remove old generated amounts.
    with engine.connect() as c:rows=c.execute(select(quotes_table)).all()
    for row in rows:
        if not is_archive(row):continue
        old=json.loads(row.payload)
        if old.get('archive_schema_version')==2:
            repaired=json.loads(row.payload);changed=False
            import extraction
            if old.get('source_snapshot_version')!=2:
                try:source=extraction.extract(STORAGE/'files'/Path(old['source_url']).name,allow_external=False)
                except Exception:source={}
                if source.get('original_fields'):
                    repaired['original_fields']=source['original_fields'];repaired['source_snapshot_version']=2;changed=True
            if not old.get('customer_contact') and Path(old.get('source_url','')).suffix.lower() in ('.xls','.xlsx'):
                try:parsed,_=extraction.read_spreadsheet(STORAGE/'files'/Path(old['source_url']).name)
                except Exception:parsed={}
                if parsed.get('customer_contact'):
                    repaired['customer_contact']=parsed['customer_contact'];changed=True
            if changed:
                repaired['version']=old.get('version',1)+1;save(repaired,previous=old)
            continue
        q=json.loads(row.payload);inferred=q.get('tax_inferred',False)
        import extraction
        try:source=extraction.extract(STORAGE/'files'/Path(q['source_url']).name,allow_external=False)
        except Exception:source={}
        if inferred:
            corrected_rate=q.get('tax_rate') if q.get('tax_rate') not in (10,None) else None
            q.update(tax_rate=corrected_rate if corrected_rate is not None else source.get('tax_rate'),tax=source.get('tax'),total=source.get('total'))
        if q.get('source_total') is not None:
            key='subtotal' if q.get('source_total_kind')=='subtotal' else 'total'
            q[key]=q['source_total']
        elif q.get('extraction_method','').startswith('local-spreadsheet'):
            q.update(subtotal=source.get('subtotal'),total=source.get('total'),tax=source.get('tax'),tax_rate=q.get('tax_rate') if q.get('tax_rate') not in (10,None) else source.get('tax_rate'))
        # Generated identifiers were never present in the uploaded source.
        if re.fullmatch(r'Q-\d{8}-[A-F0-9]{5}',q.get('number','')) and q['number'] not in q.get('source_text',''):q['number']=''
        q['source_text']=extraction.sanitize_pdf(q.get('source_text',''))
        q['tax_note']=source.get('tax_note') or ('VAT 별도' if q.get('source_total_kind')=='subtotal' or 'VAT별도' in re.sub(r'\s+','',q.get('source_text','')) else '원본 미기재')
        q.setdefault('customer_contact',source.get('customer_contact') or extraction.header(q.get('source_text','')).get('customer_contact',''))
        for it in q.get('items',[]):
            if it.get('option_group'):continue
            match=next((original for original in source.get('items',[]) if original.get('option_group') and (original.get('name')==it.get('name') or original.get('original_text')==it.get('original_text'))),None)
            if match:it['option_group']=match['option_group']
        q['original_fields']=source.get('original_fields') or {key:q.get(key) for key in ('number','customer','contact','phone','project_name','issue_date','subtotal','tax_rate','tax','total','source_total','items')}
        q['source_snapshot_version']=2
        q['review_status']='pending';q['acknowledged_warnings']=False
        clean_warnings=[]
        for warning in q.get('extraction_warnings') or []:
            if '선택' in warning and ('삭제' in warning or '포함할' in warning or '선택해야' in warning):warning='대체 옵션이 포함된 원본입니다. 모든 옵션과 원본의 선택 조건을 보존합니다.'
            if '10%' in warning and ('기본' in warning or '적용' in warning):continue
            clean_warnings.append(warning)
        q['archive_schema_version']=2;q['extraction_warnings']=list(dict.fromkeys(clean_warnings+['기존 작성 기능에서 생성한 계산금액은 제거했습니다. 원본과 정정값을 확인해주세요.']))
        q['version']=old.get('version',1)+1
        save(calculate(q),previous=old)
