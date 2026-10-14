"""Capture explicit people and contact blocks; PDF evidence comes from rendered pixels."""
from __future__ import annotations
import hashlib
import re

VERSION=3
FIELDS=('name','company','department','title','role','phone','mobile','email','fax','address')
ALIASES={'name':['성명','이름','Name'], 'company':['소속회사','소속 회사','소속','회사'], 'department':['부서','부서명','소속부서'], 'title':['직함','직책','직위'], 'role':['담당역할','담당 역할'], 'phone':['연락처','연 락 처','전화','전화번호','TEL','Telephone'], 'mobile':['휴대전화','휴대폰','핸드폰','Mobile','H.P','HP','M'], 'email':['이메일','E-MAIL','E - M AIL','E - M AI L','EMAIL','MAIL'], 'fax':['팩스','FAX'], 'address':['주소','소재지']}
NAME_LABELS=['견적담당자','발행담당자','담당자','담 당 자','참조','참 조','參照','參 照','대표자','대표이사','대표 이사','代 表 理 事','수신인','성명','이름','Name','Contact','Attn']
EMAIL=re.compile(r'[\w.+-]+\s*@\s*[\w.-]+\s*\.\s*[A-Za-z]{2,}')
PHONE=re.compile(r'(?<!\d)(?:\+82[- ]?)?0\d{1,2}[- )]*\d{3,4}[- ]*\d{4}(?!\d)')
TITLE=re.compile(r'\s*(대표이사|대표|이사|상무|전무|부장|차장|과장|대리|주임|사원|팀장|실장|매니저|프로|Manager|Director)(?:님)?(?:\s*귀하|\s*貴下)?\s*$',re.I)


def blank(source=None):
    result={field:'' for field in FIELDS}
    result.update(id='',additional_attributes=[],source_records=[],review_status='pending',origin='source')
    return result


def parse_blocks(blocks):
    records=[];evidence=[]
    labels=sorted({a for values in ALIASES.values() for a in values},key=len,reverse=True)
    lookup={re.sub(r'\s','',label).casefold():key for key,aliases in ALIASES.items() for label in aliases}
    field_pattern=re.compile(r'(?<![\w가-힣])('+ '|'.join(re.escape(label) for label in labels)+r')\s*[:：]\s*',re.I)
    name_pattern=re.compile(r'(?<![\w가-힣])('+ '|'.join(re.escape(label) for label in sorted(NAME_LABELS,key=len,reverse=True))+r')\s*(?:[:：]\s*|\s+)(.+)',re.I)
    marker_pattern=re.compile(r'(?<![\w가-힣])('+ '|'.join(re.escape(label) for label in sorted(NAME_LABELS,key=len,reverse=True))+r')\s*(?:[:：]\s*|\s+)',re.I)
    def put(record,key,val):
        val=val.strip().strip(' /|')
        if not val:return
        if not record[key]:record[key]=val
        elif val not in record[key].split(' ; '):record[key]+=' ; '+val
    def finish(record):
        if record and any(record[key] for key in FIELDS):
            raw=str(record['source_records'])+'|'+record['name']+'|'+record['role']
            record['id']=hashlib.sha256(raw.encode()).hexdigest()[:24]
            records.append(record)
    for block in blocks:
        current=None
        entries=[]
        for line_number,line in enumerate(block['text'].splitlines(),1):
            markers=list(marker_pattern.finditer(line))
            if len(markers)>1:
                if line[:markers[0].start()].strip():entries.append((line_number,line[:markers[0].start()]))
                entries.extend((line_number,line[m.start():markers[j+1].start() if j+1<len(markers) else len(line)]) for j,m in enumerate(markers))
            else:entries.append((line_number,line))
        for line_number,line in entries:
            source={**block['source'],'line':line_number,**block.get('line_sources',{}).get(line_number,{})}
            if any(token in line for token in ('[연락처 원본 확인]','[담당자·연락처','[대표자 정보')):continue
            name_match=name_pattern.search(line)
            labelled=list(field_pattern.finditer(line))
            additional=list(re.finditer(r'(생년월일|자격|직원번호|사번|내선번호|웹사이트)\s*[:：]\s*([^/|]+)',line))
            emails=[re.sub(r'\s','',m.group()) for m in EMAIL.finditer(line)]
            phones=[m.group().strip() for m in PHONE.finditer(line)]
            if not name_match and not labelled and not emails and not phones and not additional:continue
            # Currency, item specifications and dates are not personal contact data.
            if not name_match and not emails and not phones and not additional and not any(re.sub(r'\s','',m.group(1)).casefold() in lookup for m in labelled):continue
            evidence.append(dict(text=line,source=source))
            if name_match:
                finish(current);current=blank()
                label=name_match.group(1);raw=name_match.group(2)
                raw=re.split(r'\s*(?:TEL|FAX|E-?MAIL|전화|연락처|휴대폰|이메일|부서|직함)\s*[:：]',raw,1,flags=re.I)[0].strip().rstrip('/|')
                raw=re.split(r'귀하|貴下|견적일자|작성일|견적번호|연\s*락\s*처|E\s*[- ]?\s*M\s*A\s*I\s*L|\[PAYMENT',raw,1,flags=re.I)[0].strip()
                raw=EMAIL.sub('',raw);raw=PHONE.sub('',raw).strip()
                raw=re.sub(r'\s*(?:귀하|貴下)\s*$','',raw)
                title=TITLE.search(raw)
                if title:current['title']=title.group(1);raw=raw[:title.start()].strip()
                current['name']=raw
                clean_label=re.sub(r'\s','',label)
                current['role']='고객 참조' if clean_label in ('참조','參照','Attn') else '대표자' if '대표' in label or '代' in label else '견적 담당자' if label in ('견적담당자','발행담당자') else '담당자'
            if current is None:current=blank()
            if not current['name'] and (phones or emails):
                candidate=re.match(r'^\s*([가-힣]{2,5}?)\s*(대표이사|이사|부장|차장|과장|대리|팀장|프로)(?:님)?(?=\s|\d|$)',line)
                if candidate:current['name']=candidate.group(1);current['title']=candidate.group(2)
            for j,m in enumerate(labelled):
                key=lookup[re.sub(r'\s','',m.group(1)).casefold()]
                raw=line[m.end():labelled[j+1].start() if j+1<len(labelled) else len(line)].strip()
                if re.sub(r'[\[\]\s]','',raw).upper() in ('PAYMENT','DELIVERY','SHIPTO','DATE'):continue
                if key!='name':put(current,key,raw)
            # Other explicitly labelled personal attributes stay in the person block.
            for m in additional:
                current['additional_attributes'].append(dict(label=m.group(1),value=m.group(2).strip(),source=source))
            for email in emails:put(current,'email',email)
            for phone in phones:
                key='fax' if re.search(r'FAX|팩스',line,re.I) and not re.search(r'TEL|전화|휴대',line,re.I) else 'mobile' if re.match(r'01[016789]',phone) else 'phone'
                if not any(phone in current[field] for field in ('phone','mobile','fax')):put(current,key,phone)
            current['source_records'].append(dict(source=source,text=line))
        finish(current)
    # Repeated headers are collapsed only when every personal value agrees.
    unique={}
    for record in records:
        signature=tuple(record[field] for field in FIELDS)
        if signature in unique:unique[signature]['source_records'].extend(record['source_records'])
        else:unique[signature]=record
    return list(unique.values()),evidence


def capture_people(path,q):
    blocks=[];content=q.get('document_content',{});warnings=[]
    if path.suffix.lower()=='.pdf':
        import pdfplumber
        from extraction import ocr
        if q.get('people_version',0)>=2 and q.get('personal_visible_pages'):
            blocks=q['personal_visible_pages']
        else:
            with pdfplumber.open(path) as doc:
                for index,page in enumerate(doc.pages,1):
                    # A covered PDF text layer is never a contact source.
                    text=ocr(page.to_image(resolution=200).original,upright=True)
                    blocks.append(dict(text=text,source={'page':index,'method':'visible-ocr'}))
        warnings.append('PDF 인적 사항은 화면의 문자 인식 결과입니다. 원본과 대조하고 가려지거나 흐린 값은 직접 확인해주세요.')
    elif content.get('sheets'):
        for sheet in content['sheets']:
            rows={}
            for cell in sheet['cells']:
                rows.setdefault(cell['row'],[]).append(cell)
            lines=[];line_sources={}
            for row,cells in sorted(rows.items()):
                cells.sort(key=lambda c:c['column'])
                values=[str(c['value']) for c in cells if c.get('value') not in (None,'')]
                # Label and its adjacent value are kept on one source row.
                label_set={re.sub(r'\s','',a).casefold() for a in NAME_LABELS+[a for aliases in ALIASES.values() for a in aliases]}
                chunks=[];j=0
                while j<len(values):
                    if re.sub(r'\s','',values[j]).casefold() in label_set and j+1<len(values):chunks.append(values[j]+' : '+values[j+1]);j+=2
                    else:chunks.append(values[j]);j+=1
                text=' / '.join(chunks)
                lines.append(text);line_sources[len(lines)]={'sheet':sheet['name'],'row':row,'cells':[c['address'] for c in cells],'hidden':sheet.get('state')!='visible' or any(c.get('row_hidden') or c.get('column_hidden') for c in cells)}
            blocks.append(dict(text='\n'.join(lines),source={'sheet':sheet['name']},line_sources=line_sources))
    elif content.get('blocks'):
        grouped={}
        for block in content['blocks']:
            text=block.get('text','') if block['kind']=='paragraph' else '\n'.join(' : '.join(str(v) for v in row if v) for row in block['rows'])
            group=grouped.setdefault(block['location'],dict(lines=[],sources={}))
            for line in text.splitlines():
                group['lines'].append(line);group['sources'][len(group['lines'])]={'block':block['index'],'location':block['location']}
        blocks.extend(dict(text='\n'.join(group['lines']),source={'location':location},line_sources=group['sources']) for location,group in grouped.items())
    else:
        blocks=[dict(text=q.get('document_content',{}).get('text') or q.get('source_text',''),source={'method':'ocr'})]
    people,evidence=parse_blocks(blocks)
    if any(not person['name'] for person in people):warnings.append('이름이 확인되지 않은 연락처가 있습니다. 누구의 정보인지 원본에서 확인해주세요.')
    if any(person['email'] and any(not EMAIL.fullmatch(part.strip()) for part in person['email'].split(' ; ')) for person in people):warnings.append('이메일 형식이 불명확한 문자 인식 결과가 있습니다. 원문 값은 보존했으며 원본 대조가 필요합니다.')
    # Existing reviewed fields are also preserved, explicitly separated from source OCR.
    for name_key,role,company in [('customer_contact','고객 참조',q.get('customer','')),('contact','발행 담당자',q.get('issuer',''))]:
        if path.suffix.lower()=='.pdf' and q.get('review_status')!='confirmed':continue
        name=q.get(name_key,'').strip()
        if name and not any(person['name'] and person['name'] in name for person in people):
            person=blank();person.update(name=name,role=role,company=company,origin='registered',id=hashlib.sha256(name_key.encode()).hexdigest()[:24])
            title=TITLE.search(name)
            if title:person.update(name=name[:title.start()].strip(),title=title.group(1))
            if name_key=='contact':person.update(phone=q.get('phone',''),email=q.get('email',''))
            person['source_records']=[dict(source={'field':name_key},text=name)]
            people.append(person)
    return dict(people_records=people,personal_source_blocks=evidence,personal_visible_pages=blocks if path.suffix.lower()=='.pdf' else [],people_version=VERSION,people_warnings=warnings)
