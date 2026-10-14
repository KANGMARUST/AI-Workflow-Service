"""Browse stored values by their field category, with document/person provenance."""
import re

PERSON={'fax':'팩스','phone':'전화','mobile':'휴대전화','email':'이메일','name':'이름','company':'소속 회사','department':'부서','title':'직함 / 직위','role':'담당 역할','address':'주소'}
QUOTE={'customer':'거래처','issuer':'발행 회사','number':'견적번호','project_name':'제목 / 프로젝트','issue_date':'작성일','valid_until':'유효기간','delivery':'납기','ship_to':'납품 장소','payment_terms':'결제 조건','currency':'통화','tax_note':'VAT 조건','subtotal':'공급가액','tax_rate':'세율','tax':'세액','total':'총액','notes':'비고'}
ITEM={'name':'품목명','specification':'규격','unit':'단위','quantity':'수량','unit_price':'단가','amount':'품목 금액','option_group':'선택 조건'}
DETAIL_KEYS={'issuer':'issuer','customer':'customer','number':'number','project':'project_name','issue_date':'issue_date','validity':'valid_until','currency':'currency','delivery':'delivery','ship_to':'ship_to','payment':'payment_terms','fax':'fax','address':'address','representative':'name','customer_contact':'name','notes':'notes'}


def browse(quotes):
    categories={};rows={};seen=set()
    def contact_value(key,value):
        text=re.split(r'\s+(?:TEL|FAX|M|H\.?P|MOBILE|MAIL|E-?MAIL|전화|팩스|휴대전화|휴대폰|이메일)\s*[:：]',str(value),1,flags=re.I)[0].strip()
        return re.sub(r'\D','',text) if key in ('fax','phone','mobile') else text.casefold()
    def already_personal(q,key,value):
        if key not in PERSON:return False
        return any(p.get(key) and (contact_value(key,value)==contact_value(key,p[key]) if key in ('fax','phone','mobile','email') else str(value).strip() in str(p[key]) or str(p[key]) in str(value)) for p in q.get('people_records',[]))
    def register(key,label,group):
        categories.setdefault(key,dict(key=key,label=label,group=group,count=0))
        rows.setdefault(key,[])
    for key,label in PERSON.items():register(key,label,'인적 사항')
    for key,label in QUOTE.items():register(key,label,'견적 정보')
    for key,label in ITEM.items():register('item.'+key,label,'품목 정보')
    def add(q,key,label,group,val,person='',role='',source=None,item_index=None,origin='source'):
        register(key,label,group)
        if val is None or str(val).strip()=='':return
        value=str(val).strip()
        if '원본 확인]' in value:return
        if key in ('fax','phone','mobile','email'):
            value=re.split(r'\s+(?:TEL|FAX|M|H\.?P|MOBILE|MAIL|E-?MAIL|전화|팩스|휴대전화|휴대폰|이메일)\s*[:：]',value,1,flags=re.I)[0].strip()
        # Formatting variations must not duplicate a fax/phone from the same owner.
        normalized=re.sub(r'\D','',value) if key in ('fax','phone','mobile') else re.sub(r'\s+',' ',value).casefold()
        signature=(q['id'],key,person,item_index,normalized)
        if signature in seen:return
        seen.add(signature)
        rows[key].append(dict(value=value,quote_id=q['id'],quote_title=q.get('project_name') or q.get('source_name') or '제목 미기재',source_name=q.get('source_name',''),source_url=q.get('source_url',''),customer=q.get('customer',''),issue_date=q.get('issue_date',''),person_name=person,person_role=role,source=source or {},item_index=item_index,origin=origin,currency=q.get('currency','KRW')))
    for q in quotes:
        for key,label in QUOTE.items():add(q,key,label,'견적 정보',q.get(key),source={'field':key},origin='registered')
        for person in q.get('people_records',[]):
            source=(person.get('source_records') or [{}])[0].get('source',{})
            for key,label in PERSON.items():
                # Several explicit contacts are saved independently for browsing.
                values=str(person.get(key) or '').split(' ; ')
                for val in values:add(q,key,label,'인적 사항',val,person.get('name',''),person.get('role',''),source,origin=person.get('origin','source'))
            for attr in person.get('additional_attributes',[]):add(q,'person.'+attr['label'],attr['label'],'인적 사항',attr['value'],person.get('name',''),person.get('role',''),attr.get('source',source))
        for key,owner in [('phone','contact'),('email','contact'),('name','contact'),('name','customer_contact')]:
            val=q.get(owner) if key=='name' else q.get(key)
            if val and not any(p.get(key) and (str(val) in str(p[key]) or str(p[key]) in str(val)) for p in q.get('people_records',[])):
                add(q,key,PERSON[key],'인적 사항',val,q.get(owner,''),source={'field':owner},origin='registered')
        for field in q.get('detailed_fields',[]):
            key=DETAIL_KEYS.get(field['key'],'detail.'+field['category']+'.'+field['key'])
            if already_personal(q,key,field['value']):continue
            add(q,key,PERSON.get(key,QUOTE.get(key,field['label'])),'인적 사항' if key in PERSON else '세부 조건',field['value'],source=field.get('source',{}),origin=field.get('origin','source'))
        from people_capture import ALIASES
        aliases={re.sub(r'\s','',alias).casefold():key for key,names in ALIASES.items() for alias in names}
        for field in q.get('extra_fields',[]):
            label=field.get('label','').strip()
            if not label or label in ('시트','페이지'):continue
            if field.get('original_text') and (label.startswith(('-','(')) or 'PAGE' in label.upper() or any(str(field.get('value') or '').strip() in attr['value'] for it in q.get('item_specifications',[]) for attr in it['attributes'])):continue
            key=aliases.get(re.sub(r'\s','',label).casefold(),'extra.'+label)
            if already_personal(q,key,field.get('value','')):continue
            add(q,key,PERSON.get(key,label),'인적 사항' if key in PERSON else '추가 정보',field.get('value'),source={'line':field.get('source_line',1)},origin='registered')
        for index,item in enumerate(q.get('items',[])):
            for key,label in ITEM.items():add(q,'item.'+key,label,'품목 정보',item.get(key),source={'item_index':index},item_index=index,origin='registered')
        for spec in q.get('item_specifications',[]):
            for attr in spec['attributes']:add(q,'spec.'+attr['label'],attr['label'],'품목 사양',attr['value'],source=attr['source'],item_index=spec['item_index'],origin='registered')
    for key,values in rows.items():categories[key]['count']=len(values)
    return list(categories.values()),rows
