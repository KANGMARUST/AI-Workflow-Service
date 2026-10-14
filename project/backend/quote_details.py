"""Explicit source labels, their values and provenance, without inferred facts."""
import hashlib
import re

VERSION=1
GROUPS={'supplier':'공급자 정보','buyer':'고객 정보','quotation':'견적 식별·일자','terms':'거래·보증 조건','charges':'할인·추가 비용','notes':'비고·특약','specification':'품목 사양'}
ALIASES={
 'supplier':{'issuer':['공급사','공급자','발행회사','상호','회사명'],'business_number':['사업자등록번호','사업자번호','등록번호'], 'address':['주소','소재지'], 'business_type':['업태'],'business_item':['종목'], 'fax':['팩스','FAX'],'representative':['대표자','대표이사'],'website':['홈페이지','웹사이트']},
 'buyer':{'customer':['수신','受信','거래처','고객사','customer'],'customer_contact':['참조','參照'],'department':['부서','고객부서']},
 'quotation':{'number':['견적번호','문서번호'],'project':['프로젝트명','프로젝트','題目','제목'],'issue_date':['작성일','견적일자','발행일자','發行日字'],'validity':['유효기간','有效期間'],'currency':['통화']},
 'terms':{'delivery':['납기','예정납기','豫定納期'],'ship_to':['납품장소','배송지','納品場所'],'payment':['결제조건','지불조건','支拂條件'],'warranty':['보증기간','보증조건','Warranty','보증'],'transport':['운송조건','배송조건','인도조건','인코텀즈'],'installation':['설치조건','설치범위'],'exclusions':['제외사항','제외항목'],'maintenance':['유지보수','유지보수조건'],'inspection':['검수조건','검수'],'packaging':['포장조건'],'origin':['원산지']},
 'charges':{'discount':['할인','할인율','할인금액'],'shipping':['배송비','운송비'],'installation_cost':['설치비'],'other_cost':['추가비용','기타비용'],'tax_condition':['VAT','부가세조건']},
 'notes':{'notes':['비고','備考','특기사항','특이사항'],'special_terms':['특약','추가조건','유의사항'],'option':['선택조건','선택옵션']}}


def norm(label):return re.sub(r'[\s()·.：:]','',label).casefold()


LOOKUP={norm(label):(group,key,label) for group,fields in ALIASES.items() for key,labels in fields.items() for label in labels}


def location_text(source):
    if source.get('sheet'):return f"시트 {source['sheet']} / {source.get('cell','')}"
    if source.get('page'):return f"{source['page']}페이지 / {source.get('line',1)}줄"
    if source.get('block'):return f"{source.get('location','본문')} / 문단 {source['block']}"
    return f"원문 {source.get('line',1)}줄"


def extract_details(q):
    fields=[];seen=set();content=q.get('document_content',{})
    def add(group,key,label,raw,source,original):
        raw=str(raw).strip()
        if not raw or '[담당자' in raw or '[연락처 원본 확인]' in raw or '[이메일 원본 확인]' in raw:return
        identity=(group,key,raw)
        if identity in seen:return
        seen.add(identity)
        token=hashlib.sha256((group+'|'+key+'|'+str(source)).encode()).hexdigest()[:20]
        fields.append(dict(id=token,category=group,key=key,label=label,value=raw,source=source,original_text=original,origin='source'))
    labels=sorted((label for fields_ in ALIASES.values() for aliases in fields_.values() for label in aliases),key=len,reverse=True)
    pattern=re.compile(r'(?<![\w가-힣])('+ '|'.join(re.escape(label) for label in labels)+r')\s*[:：]\s*',re.I)
    def lines(text,source):
        raw_lines=text.splitlines()
        for index,line in enumerate(raw_lines,1):
            src={**source,'line':index}
            matches=list(pattern.finditer(line))
            if matches:
                for j,m in enumerate(matches):
                    group,key,label=LOOKUP[norm(m.group(1))]
                    value=line[m.end():matches[j+1].start() if j+1<len(matches) else len(line)].strip().rstrip(' /|')
                    add(group,key,label,value,src,line)
            else:
                normalized=norm(line)
                if normalized in LOOKUP and index<len(raw_lines):
                    group,key,label=LOOKUP[normalized];value=raw_lines[index].strip()
                    if norm(value) not in LOOKUP:add(group,key,label,value,src,line+'\n'+value)
    for page in content.get('pages',[]):lines(page.get('text',''),{'page':page['number']})
    for block in content.get('blocks',[]):
        source={'block':block['index'],'location':block['location']}
        if block['kind']=='paragraph':lines(block.get('text',''),source)
        else:
            for row_index,row in enumerate(block.get('rows',[]),1):
                for j,cell in enumerate(row):
                    if norm(cell) in LOOKUP:
                        following=next((str(v).strip() for v in row[j+1:] if v and norm(str(v)) not in LOOKUP),'')
                        group,key,label=LOOKUP[norm(cell)];add(group,key,label,following,{**source,'row':row_index,'column':j+1},' | '.join(row))
    for sheet in content.get('sheets',[]):
        rows={}
        for cell in sheet['cells']:rows.setdefault(cell['row'],[]).append(cell)
        for cells in rows.values():
            cells.sort(key=lambda c:c['column'])
            for j,cell in enumerate(cells):
                raw=cell.get('value')
                if raw is None:continue
                source={'sheet':sheet['name'],'cell':cell['address'],'hidden':sheet.get('state')!='visible' or cell.get('row_hidden',False) or cell.get('column_hidden',False)}
                if norm(str(raw)) in LOOKUP:
                    group,key,label=LOOKUP[norm(str(raw))]
                    following=next((c for c in cells[j+1:] if c.get('value') not in (None,'') and norm(str(c['value'])) not in LOOKUP),None)
                    if following:
                        add(group,key,label,following['value'],{**source,'value_cell':following['address']},str(raw)+' '+str(following['value']))
                else:lines(str(raw),source)
    if not content.get('pages') and not content.get('blocks') and not content.get('sheets'):lines(q.get('source_text',''),{})
    # Reviewed standard fields can supplement sparse layouts, but remain visibly marked.
    for field,group,key,label in [('issuer','supplier','issuer','발행 회사'),('customer','buyer','customer','거래처'),('customer_contact','buyer','customer_contact','고객 참조 담당자'),('number','quotation','number','견적번호'),('project_name','quotation','project','프로젝트'),('issue_date','quotation','issue_date','작성일'),('delivery','terms','delivery','납기'),('ship_to','terms','ship_to','납품 장소'),('payment_terms','terms','payment','결제 조건'),('valid_until','quotation','validity','유효기간')]:
        if q.get(field) and not any(f['category']==group and f['key']==key for f in fields):
            add(group,key,label,q[field],{'field':field},str(q[field]))
            if fields and fields[-1]['source']=={'field':field}:fields[-1]['origin']='registered'
    specs=[]
    for index,it in enumerate(q.get('items',[])):
        text=it.get('specification','')
        attrs=[]
        for line_number,line in enumerate(text.splitlines(),1):
            cleaned=re.sub(r'^\s*[-•]\.?\s*','',line)
            matches=list(re.finditer(r'(?<!\w)(CPU|Memory|RAM|SSD|HDD|Display|O/S|OS|Warranty|제조사|모델|모델명|재질|크기|치수|전압|용량|수량|보증|색상|무게|연결단자|사이즈|패널타입)\s*[:：]\s*',cleaned,re.I))
            if not matches:matches=list(re.finditer(r'^([^:：]{1,80}?)\s*[:：]\s*',cleaned))
            if matches:
                for j,m in enumerate(matches):
                    raw=cleaned[m.end():matches[j+1].start() if j+1<len(matches) else len(cleaned)].strip().rstrip(' /')
                    if raw:attrs.append(dict(label=m.group(1).strip(),value=raw,source={'item_index':index,'specification_line':line_number},original_text=line))
            elif cleaned.strip():attrs.append(dict(label='추가 사양',value=cleaned.strip(),source={'item_index':index,'specification_line':line_number},original_text=line))
        specs.append(dict(item_index=index,name=it.get('name',''),attributes=attrs))
    return dict(detailed_fields=fields,item_specifications=specs,details_version=VERSION)
