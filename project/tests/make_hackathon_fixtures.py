"""Invented quotation PDFs and answer key for Studio evaluation. No company data."""
import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests'/'fixtures'/'hackathon'
OUT.mkdir(parents=True,exist_ok=True)
font=ROOT/'backend'/'fonts'/'NanumGothic-Regular.ttf'
pdfmetrics.registerFont(TTFont('QuoteFixture',str(font)))

DOCS={
 '일반_과거.pdf':('일반 품목 견적',[
  '발행: 가상 장비사 / 수신: 가상 연구소 / 작성일: 2025-01-10',
  '통화: KRW / VAT 별도 / 납기: 발주 후 3주 / 결제: 납품 후 30일',
  '품목 1: 광학 모듈 OM-100 / 규격 10 mm / 수량 2 개 / 단가 100,000 KRW / 금액 200,000 KRW',
  '공급가액: 200,000 KRW / VAT: 원문 미기재',
  '보증: 납품 후 1년']),
 '일반_현재.pdf':('일반 품목 견적',[
  '발행: 가상 장비사 / 수신: 가상 연구소 / 작성일: 2026-01-10',
  '통화: KRW / VAT 별도 / 납기: 발주 후 4주 / 결제: 납품 후 30일',
  '품목 1: 광학 모듈 OM-100 / 규격 10 mm / 수량 2 개 / 단가 120,000 KRW / 금액 240,000 KRW',
  '공급가액: 240,000 KRW / VAT: 원문 미기재']),
 '대체옵션.pdf':('대체 옵션 견적',[
  '발행: 가상 옵션사 / 수신: 가상 연구소 / 작성일: 2026-02-01',
  '통화: KRW / VAT 별도',
  '다음 A, B는 대체 옵션이며 한 가지만 발주자가 선택한다. 선택 전 총액은 확정되지 않는다.',
  '옵션 A: 저장 장치 SSD-1 / 규격 1 TB / 수량 1 개 / 단가 100,000 KRW / 금액 100,000 KRW',
  '옵션 B: 저장 장치 SSD-2 / 규격 2 TB / 수량 1 개 / 단가 180,000 KRW / 금액 180,000 KRW',
  '총액: 옵션 선택 후 결정 / 납기: 선택 후 통보']),
 '패키지.pdf':('패키지·구성품 견적',[
  '발행: 가상 패키지사 / 수신: 가상 연구소 / 작성일: 2026-03-01',
  '통화: KRW / VAT 포함',
  '품목 1: 분석 패키지 PK-10 / 수량 1 세트 / 단가 500,000 KRW / 금액 500,000 KRW',
  '구성품 1-1: 제어기 CT-1 / 수량 1 개 / 금액 300,000 KRW / 패키지 금액에 포함',
  '구성품 1-2: 센서 SN-2 / 수량 2 개 / 금액 200,000 KRW / 패키지 금액에 포함',
  '총액: 500,000 KRW / 구성품 금액을 패키지에 더하지 않는다']),
 '혼합.pdf':('옵션·패키지 혼합 견적',[
  '발행: 가상 혼합사 / 수신: 가상 연구소 / 작성일: 2026-04-01',
  '통화: USD / VAT 원문 미기재',
  '기본 패키지 MX-1: 본체 1 세트 / 1,000 USD',
  '구성품: 전원 장치 PS-1 / 본체 패키지 금액에 포함',
  '대체 옵션 A: 센서 S-1 / 1 개 / 100 USD',
  '대체 옵션 B: 센서 S-2 / 1 개 / 180 USD',
  '센서는 A 또는 B 하나만 선택한다. 최종 금액은 미기재']),
 '비교_두문서.pdf':('두 문서 비교 입력',[
  '문서 1 / ID: past / 일반_과거.pdf / 작성일 2025-01-10',
  '광학 모듈 OM-100 / 규격 10 mm / 수량 2 개 / 단가 100,000 KRW / VAT 별도 / 납기 3주',
  '문서 2 / ID: current / 일반_현재.pdf / 작성일 2026-01-10',
  '광학 모듈 OM-100 / 규격 10 mm / 수량 2 개 / 단가 120,000 KRW / VAT 별도 / 납기 4주',
  '두 문서의 품목 대응과 납기 차이를 확인한다. 통화 환산은 하지 않는다.'])}

for filename,(kind,lines) in DOCS.items():
    c=Canvas(str(OUT/filename),pagesize=A4)
    c.setTitle('가상 견적: '+kind)
    c.setFont('QuoteFixture',16);c.drawString(40,800,'가상 견적서 · '+kind)
    c.setFont('QuoteFixture',10)
    for index,line in enumerate(lines):c.drawString(40,760-index*35,line)
    c.save()

truth={filename:{'document_type':kind,'lines':lines} for filename,(kind,lines) in DOCS.items()}
(OUT/'answer_key.json').write_text(json.dumps(truth,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Created {len(DOCS)} invented PDFs and answer key in {OUT}')
