"""Build fictional, non-production PDFs for Studio configuration and checks."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parents[1] / "agent_configs" / "samples"
OUT.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont("Korean", "C:/Windows/Fonts/malgun.ttf"))
style = ParagraphStyle("body", fontName="Korean", fontSize=10, leading=16)

for case in ("normal", "review"):
    path = OUT / f"quote_{case}.pdf"
    story = [Paragraph("가상 견적서 - QuoteFlow 검증 전용", style), Spacer(1, 16)]
    lines = [
        "실제 거래·연락처 정보가 없는 가상 테스트 자료입니다.",
        f"견적번호: DEMO-2026-{'001' if case == 'normal' else '002'}",
        "발행 회사: 가상공급사 / 고객사: 가상제조사",
        "제목: 센서 장비 납품 / 작성일: 2026-10-16",
        "담당자: 가상담당 / 연락처: 미기재",
        "유효기간: 2026-10-31 / 납기일: 2026-11-15",
        "통화: KRW / 결제 조건: 납품 후 30일 / 납품 조건: 운송비 포함",
    ]
    story += [Paragraph(x, style) for x in lines]
    story.append(Spacer(1, 14))
    rows = [["품목명", "규격", "단위", "수량", "단가", "금액"],
            ["온도 센서", "TS-100 / -20~80C", "개", "10", "25,000", "250,000"],
            ["제어 모듈", "CM-20 / 24V", "개", "2", "100,000", "200,000"],
            ["연결 케이블", "CB-5 / 5m", "개", "5" if case == "normal" else "미기재", "10,000", "50,000"]]
    if case == "review":
        rows[2][-1] = "190,000"
    table = Table(rows, colWidths=[80, 130, 35, 40, 70, 75])
    table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "Korean"),
                              ("FONTSIZE", (0, 0), (-1, -1), 9),
                              ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef8")),
                              ("GRID", (0, 0), (-1, -1), .5, colors.grey),
                              ("TOPPADDING", (0, 0), (-1, -1), 9),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    story += [table, Spacer(1, 16)]
    story += [Paragraph(x, style) for x in [
        "공급가액: 500,000원 / 부가세: 50,000원 (10%) / 총액: 550,000원",
        "할인: 없음 / 비고: 설치 작업 제외. 품목은 모두 독립 품목.",
        "검증 메모: " + ("정상 견적. 품목 3행." if case == "normal" else
                          "제어 모듈의 기재 금액 불일치와 케이블 수량 누락을 검토 표시해야 함. 누락 수량을 역산해 채우면 안 됨."),
    ]]
    SimpleDocTemplate(str(path), rightMargin=30, leftMargin=30).build(story)
    print(path)

for kind, lines in {
    "comparison": [
        "가상 단가 비교 입력 - 실제 거래 데이터 없음",
        "문서 A: DEMO-A / 고객사: 가상제조사 / 작성일: 2026-09-01",
        "품목: 온도 센서 / 규격: TS-100 / 단위: 개 / 통화: KRW",
        "수량: 10 / 단가: 25000 / VAT 별도 / 결제: 납품 후 30일 / 운송비 포함",
        "문서 B: DEMO-B / 고객사: 가상연구소 / 작성일: 2026-10-01",
        "품목: 온도 센서 / 규격: TS-100 / 단위: 개 / 통화: KRW",
        "수량: 20 / 단가: 23000 / VAT 별도 / 결제: 선불 / 운송비 별도",
        "문서 C: DEMO-C / 고객사: 가상물류사 / 작성일: 2026-10-10",
        "품목: 온도 센서 / 규격: TS-200 / 단위: 세트 / 통화: USD",
        "수량: 1 / 단가: 100 / 세금 조건: 미기재 / 결제: 미기재",
        "사용자 요청: 같은 규격의 과거 단가와 조건을 비교하고 다른 규격은 구분해주세요.",
    ],
    "draft": [
        "가상 견적 초안 입력 - 실제 거래 데이터 없음",
        "원본 견적 ID: DEMO-A / 원본 품목: 온도 센서 / 규격: TS-100",
        "원본 조건: 단위 개 / 통화 KRW / 수량 10 / 단가 25000 / 금액 250000",
        "원본 세금 조건: VAT 별도, 세율 10% / 결제: 납품 후 30일",
        "고객사: 가상제조사 / 발행 회사: 가상공급사",
        "사용자가 확정한 변경사항: 수량 12, 적용 단가 24000, 결제 조건 유지",
        "새 견적번호: 미정 / 새 작성일: 2026-10-16 / 유효기간: 미정 / 납기: 미정",
        "출력 양식: 백엔드의 기본 양식 1개 / 상태: 담당자 검토 전 초안",
        "사용자 요청: 위 변경사항을 반영할 초안 필드를 정리하고 미정 조건을 질문해주세요.",
    ],
}.items():
    path = OUT / f"input_{kind}.pdf"
    SimpleDocTemplate(str(path)).build([Paragraph(x, style) for x in lines])
    print(path)
