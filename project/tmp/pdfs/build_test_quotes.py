from pathlib import Path
import json, subprocess
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image, ImageOps, ImageDraw
import pdfplumber

OUT=Path(r'D:\workflow AI hacker\Test_input_data')
TMP=Path(__file__).parent
POP=Path(r'C:\Users\gns03\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe')
pdfmetrics.registerFont(TTFont('KR',r'C:\Windows\Fonts\malgun.ttf'))
pdfmetrics.registerFont(TTFont('KRB',r'C:\Windows\Fonts\malgunbd.ttf'))
W,H=A4
base=[('센서 브라켓',10,'EA',12000,120000,'SUS304 / 100 x 80 mm'),('근접 센서',4,'EA',45000,180000,'DC24V / 감지 거리 8 mm'),('설치 작업',1,'식',150000,150000,'현장 설치 및 동작 점검')]
cases=[
 dict(id='T01',name='표준_부가세별도',customer='가상한빛제조',date='2026-09-02',items=base,goal='정상 추출, 거래처·품목 검색, 공급가액 450000 / 부가세 45000 / 총액 495000',tax='별도'),
 dict(id='T02',name='동일품목_단가변경',customer='가상한빛제조',date='2026-10-01',items=[('센서 브라켓',10,'EA',13500,135000,'SUS304 / 100 x 80 mm'),('근접 센서',4,'EA',47000,188000,'DC24V / 감지 거리 8 mm'),base[2]],goal='T01과 같은 품목·거래처의 날짜별 단가 비교. 공급가액 473000',tax='별도'),
 dict(id='T03',name='다른거래처_규격변경',customer='가상미래자동화',date='2026-09-15',items=[('센서 브라켓',30,'EA',18000,540000,'SUS316 / 150 x 100 mm'),('근접 센서',8,'EA',62000,496000,'DC24V / 감지 거리 15 mm')],goal='동일 품명·다른 규격 및 수량 비교. 공급가액 1036000',tax='별도'),
 dict(id='T04',name='부가세포함',customer='가상새봄물류',date='2026-10-03',items=[('바코드 리더',2,'EA',250000,500000,'USB / 2D 코드'),('통신 케이블',5,'EA',20000,100000,'CAT6 / 10 m')],goal='품목 금액은 세전. 공급가액 600000 / 부가세 60000 / VAT 포함 총액 660000',tax='포함'),
 dict(id='T05',name='대체옵션_합계없음',customer='가상미래자동화',date='2026-10-05',items=[('기본 제어반',1,'식',500000,500000,'공통 구성'),('옵션A 표준 HMI',1,'EA',350000,350000,'7 inch'),('옵션B 고급 HMI',1,'EA',650000,650000,'10 inch')],goal='모든 옵션 보존. A와 B 중 하나 선택이며 합계·세액·총액은 원본 미기재. 전체 행 합산 금지',tax='별도',no_total=True,notes=['2번 3번 중 선택 옵션: 옵션A 또는 옵션B 중 하나만 선택합니다.','최종 선택 전이므로 공급가액, 부가세, 총액은 미기재합니다.']),
 dict(id='T06',name='패키지_구성품',customer='가상한빛제조',date='2026-10-06',items=[('검사 장치 패키지',1,'식',1200000,1200000,'아래 구성품 포함'),('구성품 산업용 카메라',1,'EA',700000,700000,'패키지 포함'),('구성품 렌즈',1,'EA',200000,200000,'패키지 포함'),('구성품 설치 및 설정',1,'식',300000,300000,'패키지 포함'),('안전 센서 패키지',1,'식',400000,400000,'아래 구성품 포함'),('구성품 안전 센서',2,'EA',150000,300000,'패키지 포함'),('구성품 배선 작업',1,'식',100000,100000,'패키지 포함')],goal='상위 패키지 2개 + 구성품 5개 보존. 구성품은 중복 합산하지 않음. 공급가액 1600000',tax='별도',package=True,subtotal=1600000,notes=['구성품 금액은 상위 패키지에 포함된 내역이며 추가 청구하지 않습니다.']),
 dict(id='T07',name='금액불일치_검토필요',customer='가상새봄물류',date='2026-10-07',items=[('센서 브라켓',10,'EA',12000,119000,'SUS304 / 원본 금액 오류'),('배송비',1,'식',10000,10000,'일괄 배송')],goal='10 x 12000 = 120000과 원본 119000의 불일치 검출. 원본 119000 보존, 공급가액 129000',tax='별도',notes=['테스트용 의도적 오류: 첫 행 금액은 수량 x 단가와 1,000원 차이가 납니다.']),
 dict(id='T08',name='날짜_단가_누락',customer='가상누리설비',date=None,items=[('압력 센서',3,'EA',None,210000,'0-10 bar / 단가 미기재'),('설치 작업',1,'식',100000,100000,'현장 배선')],goal='작성일·담당자·첫 품목 단가 미기재. 금액/수량으로 단가 자동 생성 금지. 누락 품목은 수동 검토',tax='별도',missing=True,notes=['작성일, 담당자, 압력 센서 단가는 원본에 기재하지 않았습니다.']),
 dict(id='T09',name='여러페이지_품목30개',customer='가상누리설비',date='2026-10-09',items=[(f'제어 부품 {i:02d}',i%5+1,'EA',1000+i*500,(i%5+1)*(1000+i*500),f'모델 CTRL-{i:03d} / 규격 {i*10} mm') for i in range(1,31)],goal='2페이지에 걸친 30개 품목, 페이지 경계·반복 표 머리글·마지막 합계 추출',tax='별도'),
 dict(id='T10',name='스캔_OCR',customer='가상새봄물류',date='2026-10-10',items=base,goal='텍스트 레이어 없는 스캔 PDF. 한글·수량·단가·총액 OCR 검토. 공급가액 450000 / 총액 495000',tax='별도',scan=True),
]

def make(case,path):
 c=canvas.Canvas(str(path),pagesize=A4)
 c.setTitle(f"가상 테스트 견적서 {case['id']}")
 rows=case['items']; chunks=[rows[i:i+18] for i in range(0,len(rows),18)]
 def txt(x,y,s,size=10,bold=False):
  c.setFont('KRB' if bold else 'KR',size);c.setFillColorRGB(.12,.16,.22);c.drawString(x,y,str(s))
 for page,chunk in enumerate(chunks,1):
  c.setFillColorRGB(.09,.22,.35);c.rect(36,H-88,W-72,50,fill=1,stroke=0)
  c.setFillColorRGB(1,1,1);c.setFont('KRB',23);c.drawString(52,H-72,'견 적 서')
  txt(36,H-108,'가상 테스트 데이터 / 실제 발행 문서 아님',9,True)
  y=H-135
  headers=[f"견적번호: TEST-{case['id']}-2026",f"수신: {case['customer']}",f"참조: 가상이담당 귀하",f"프로젝트명: 설비 개선 {case['name']}"]
  if case['date']:headers.append(f"작성일: {case['date']}")
  if not case.get('missing'):headers.append('담당자: 가상김영업')
  headers+=['공급사: 가상 테스트 공급사',f"VAT {case['tax']} / 세율 10% / 통화 KRW"]
  for line in headers:txt(36,y,line);y-=18
  y-=14
  xs=[40,70,325,363,440,515]
  c.setFillColorRGB(.90,.94,.97);c.rect(36,y-7,W-72,26,fill=1,stroke=0)
  for x,label in zip(xs,['번호','품명 / 규격','수량','단위','단가','금액']):txt(x,y,label,9,True)
  y-=27
  for index,row in enumerate(chunk,(page-1)*18+1):
   name,qty,unit,price,amt,spec=row
   idx='' if case.get('package') and name.startswith('구성품') else str(index)
   txt(40,y,idx,9);txt(70,y,name,9);txt(325,y,qty,9);txt(363,y,unit,9)
   c.setFont('KR',9);c.drawRightString(490,y,'' if price is None else f'{price:,}');c.drawRightString(W-40,y,f'{amt:,}')
   txt(70,y-11,'-. '+spec,8)
   c.setStrokeColorRGB(.85,.88,.91);c.line(36,y-16,W-36,y-16);y-=25
  if page==len(chunks):
   y-=12
   if not case.get('no_total'):
    subtotal=case.get('subtotal',sum(row[4] for row in rows));tax=round(subtotal*.1)
    for label,value in [('공급가액',subtotal),('부가세',tax),('총액',subtotal+tax)]:
     txt(370,y,label,10,True);c.setFont('KRB',11);c.drawRightString(W-40,y,f'{value:,}');y-=21
   for line in case.get('notes',[]):txt(36,y-8,line,8);y-=17
   txt(36,y-16,'납기: 발주 후 14일 / 결제조건: 검수 후 30일 / 유효기간: 견적일로부터 30일',8)
  txt(36,25,f"TEST ONLY / {case['id']} / {page} / {len(chunks)}",8)
  c.showPage()
 c.save()

OUT.mkdir(exist_ok=True)
manifest=[];previews=[]
for case in cases:
 path=OUT/f"{case['id']}_{case['name']}.pdf"
 if path.exists():raise FileExistsError(path)
 source=TMP/'scan_source.pdf' if case.get('scan') else path
 make(case,source)
 if case.get('scan'):
  prefix=TMP/'scan_source'
  subprocess.run([str(POP),'-r','180','-singlefile','-png',str(source),str(prefix)],check=True)
  c=canvas.Canvas(str(path),pagesize=A4);c.drawImage(str(prefix)+'.png',0,0,width=W,height=H);c.showPage();c.save()
 prefix=TMP/case['id']
 subprocess.run([str(POP),'-r','90','-png',str(path),str(prefix)],check=True)
 with pdfplumber.open(path) as doc:
  pages=len(doc.pages);text='\n'.join(p.extract_text() or '' for p in doc.pages)
  if case.get('scan'):assert not text.strip()
  else:assert case['customer'] in text and f"TEST-{case['id']}-2026" in text
  if case['id']=='T09':assert pages==2 and '제어 부품 30' in text
 manifest.append(dict(file=path.name,case_id=case['id'],purpose=case['goal'],expected_customer=case['customer'],expected_date=case['date'],expected_source_row_count=len(case['items']),expected_items=[dict(name=r[0],quantity=r[1],unit=r[2],unit_price=r[3],amount=r[4],specification=r[5]) for r in case['items']],pages=pages,scanned=bool(case.get('scan')),totals_missing=bool(case.get('no_total'))))
 previews.extend(sorted(TMP.glob(case['id']+'-*.png')))
(OUT/'expected_results.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 테스트 견적서 10개','', '모두 가상 데이터입니다. 실제 거래, 실제 회사 및 개인정보와 관계없습니다.','기존 견적서를 업로드하여 보관·추출·검색·검토하는 기능을 테스트하기 위한 원본입니다.','', '| 파일 | 확인할 내용 |','|---|---|']
for x in manifest:lines.append(f"| {x['file']} | {x['purpose']} |")
lines+=['','## 검토 기준','- expected_results.json은 원본의 정답 데이터입니다. 앱의 추출 결과와 별도로 비교하세요.','- 옵션 문서의 모든 행을 보존하되 선택 전 합계를 생성하지 마세요.','- 패키지 구성품을 상위 패키지 금액에 다시 더하지 마세요.','- 오류·누락 문서는 원본 값을 보존하고 검토 후 수정하는 흐름을 확인하세요.','- T08의 단가와 작성일은 추측으로 채우면 안 됩니다.','- T10은 텍스트 레이어가 없는 이미지 PDF입니다. OCR 결과를 원본과 비교하세요.','- 현재 앱의 PDF 추출은 담당자·전화·이메일을 자동 반영하지 않으므로 원본을 보고 확인해야 합니다.','- 이 파일들은 테스트 폴더에만 생성했으며 앱 데이터베이스에는 자동 등록하지 않았습니다.']
(OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
thumbs=[]
for p in previews:
 im=Image.open(p).convert('RGB');im.thumbnail((397,562));tile=Image.new('RGB',(417,602),'#e5e7eb');tile.paste(im,((417-im.width)//2,25));ImageDraw.Draw(tile).text((12,580),p.stem,fill='black');thumbs.append(tile)
sheet=Image.new('RGB',(417*4,602*((len(thumbs)+3)//4)),'white')
for i,tile in enumerate(thumbs):sheet.paste(tile,((i%4)*417,(i//4)*602))
sheet.save(TMP/'contact_sheet.png')
print(json.dumps({'count':len(manifest),'pages':sum(x['pages'] for x in manifest),'files':[x['file'] for x in manifest]},ensure_ascii=False))

