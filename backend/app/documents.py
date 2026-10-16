import io
import json
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal
from xml.sax.saxutils import escape

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import ROOT


class DocumentError(ValueError):
    pass


ALIASES = {
    "quote_number": ["견적번호", "quotationno", "quoteno", "견적서번호"],
    "title": ["제목", "견적명", "프로젝트명", "subject"],
    "issuer_company": ["발행회사", "공급사", "공급자", "공급업체", "issuer", "supplier"],
    "customer_name": ["고객사", "거래처", "수신회사", "customer", "client"],
    "contact_name": ["담당자", "contactname"], "contact_email": ["이메일", "email"],
    "contact_phone": ["연락처", "전화번호", "phone"],
    "issue_date": ["작성일", "발행일", "견적일", "견적일자", "issuedate"],
    "valid_until": ["유효기간", "유효일", "validuntil"], "delivery_date": ["납기일", "deliverydate"],
    "subtotal": ["공급가액", "소계", "subtotal"], "tax_amount": ["부가세", "부가가치세", "세액", "taxamount"],
    "tax_rate": ["세율", "taxrate"], "total_amount": ["총액", "합계금액", "총금액", "grandtotal", "totalamount"],
    "tax_terms": ["세금조건"], "tax_basis": ["세금기준"],
    "currency": ["통화", "currency"], "payment_terms": ["결제조건", "지급조건", "paymentterms"],
    "delivery_terms": ["납품조건", "인도조건", "deliveryterms"],
    "discount_terms": ["할인", "할인조건", "discount"], "notes": ["비고", "특이사항", "notes"],
}
ITEM_ALIASES = {
    "item_name": ["품목명", "품명", "품목", "제품명", "itemname", "description"],
    "specification": ["규격", "사양", "모델", "specification", "model"],
    "unit": ["단위", "unit"], "quantity": ["수량", "quantity", "qty"],
    "unit_price": ["단가", "unitprice"], "amount": ["금액", "품목금액", "amount", "linetotal"],
}


def norm(value):
    return re.sub(r"[\s:：()._%\-]", "", str(value if value is not None else "")).casefold()


def validate_file(data: bytes, suffix: str, max_pages: int):
    if suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise DocumentError("확장자와 PDF 내용이 일치하지 않습니다.")
        try:
            from pdfminer.pdfpage import PDFPage
            pages = list(PDFPage.get_pages(io.BytesIO(data), check_extractable=True))
            if not pages or len(pages) > max_pages:
                raise DocumentError(f"PDF는 1~{max_pages}페이지여야 합니다.")
        except DocumentError:
            raise
        except Exception as exc:
            raise DocumentError("PDF를 읽을 수 없습니다. 암호화 또는 손상 여부를 확인하세요.") from exc
    elif suffix == ".xlsx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(x.file_size for x in archive.infolist()) > 100*1024*1024 or len(archive.infolist()) > 2000:
                    raise DocumentError("압축 해제 크기 또는 항목 수가 너무 큽니다.")
                if "xl/workbook.xml" not in archive.namelist():
                    raise DocumentError("정상적인 XLSX 파일이 아닙니다.")
                if any("vbaProject" in x.filename for x in archive.infolist()):
                    raise DocumentError("매크로 포함 문서는 지원하지 않습니다.")
        except (zipfile.BadZipFile, KeyError) as exc:
            raise DocumentError("XLSX 파일이 손상되었습니다.") from exc
    else:
        raise DocumentError("현재 .xlsx와 텍스트 PDF만 지원합니다.")


def read_document(data, suffix, max_pages=100):
    validate_file(data, suffix, max_pages)
    warnings, tables, raw = [], [], []
    if suffix == ".xlsx":
        try:
            for cached in (True, False):
                workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=cached, keep_links=False)
                try:
                    if len(workbook.sheetnames) > 30:
                        raise DocumentError("시트는 최대 30개까지 지원합니다.")
                    for sheet in workbook:
                        if sheet.max_row and sheet.max_column and sheet.max_row*sheet.max_column > 100000:
                            raise DocumentError("시트 크기가 100,000셀을 초과합니다.")
                        rows, cell_count, character_count = [], 0, 0
                        for row in sheet.iter_rows():
                            cell_count += len(row)
                            if cell_count > 100000:
                                raise DocumentError("시트 크기가 100,000셀을 초과합니다.")
                            values = []
                            for cell in row:
                                v = cell.value
                                if isinstance(v, (date, datetime)):
                                    v = v.strftime("%Y-%m-%d")
                                if not cached and cell.data_type == "f":
                                    warnings.append("Excel 수식은 실행하지 않습니다. 캐시된 결과가 없으면 값 확인이 필요합니다.")
                                values.append(str(v) if v is not None else "")
                                character_count += len(values[-1])
                                if character_count > 300000:
                                    raise DocumentError("시트 텍스트가 300,000자를 초과합니다.")
                            if any(values):
                                rows.append(values)
                        if cached:
                            tables.append(rows)
                            raw.append(f"[시트: {sheet.title}]\n" + "\n".join(" | ".join(r) for r in rows))
                        else:
                            raw.append(f"[원본 수식: {sheet.title}]\n" + "\n".join(" | ".join(r) for r in rows if any(x.startswith("=") for x in r)))
                finally:
                    workbook.close()
        except DocumentError:
            raise
        except Exception as exc:
            raise DocumentError("XLSX를 읽을 수 없습니다.") from exc
    else:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for i, page in enumerate(pdf.pages):
                    raw.append(f"[페이지 {i+1}]\n" + (page.extract_text() or ""))
                    tables.extend(page.extract_tables() or [])
        except ImportError:
            from pdfminer.high_level import extract_text
            raw.append(extract_text(io.BytesIO(data)))
            warnings.append("표 파서가 없어 텍스트만 읽었습니다. 품목은 직접 확인하세요.")
        except Exception as exc:
            raise DocumentError("PDF 텍스트와 표를 추출하지 못했습니다.") from exc
    text = "\n\n".join(raw)
    if len(text) > 300000:
        raise DocumentError("추출 텍스트가 300,000자를 초과합니다.")
    if not re.search(r"[가-힣A-Za-z0-9]", re.sub(r"\[페이지 \d+\]", "", text)):
        raise DocumentError("텍스트가 없는 스캔 PDF입니다. OCR 지원은 별도 확장 범위입니다.")
    return {"text": text, "tables": tables, "warnings": sorted(set(warnings))}


def local_extract(document):
    text, tables = document["text"], document["tables"]
    result = {"raw_fields": {}, "items": []}
    for pattern, basis in ((r"(?:VAT|부가세|부가가치세)\s*별도", "exclusive"), (r"(?:VAT|부가세|부가가치세)\s*포함", "inclusive")):
        match = re.search(pattern, text, re.I)
        if match:
            result["tax_terms"], result["tax_basis"] = match[0], basis
            break
    # Explicit label/value pairs only. Never guess missing headers from arbitrary text.
    lookup = {norm(a): k for k, aliases in ALIASES.items() for a in [k, *aliases]}
    for segment in re.split(r"\n| / |\|", text):
        match = re.match(r"\s*([^:：]+)[:：]\s*(.+)", segment)
        if match and norm(match[1]) in lookup:
            key = lookup[norm(match[1])]
            result.setdefault(key, match[2].strip())
            result["raw_fields"].setdefault(key, match[2].strip())
    for table in tables:
        mapping = None
        for row in table:
            values = [str(x if x is not None else "").strip() for x in row]
            for i, value in enumerate(values[:-1]):
                key = lookup.get(norm(value))
                if key and values[i+1]:
                    result.setdefault(key, values[i+1])
                    result["raw_fields"].setdefault(key, values[i+1])
            header = {i: k for i, value in enumerate(values) for k, names in ITEM_ALIASES.items() if norm(value) in names}
            if "item_name" in header.values() and len(header) >= 2:
                mapping = header
                continue
            if mapping:
                item = {key: values[i] if i < len(values) else "" for i, key in mapping.items()}
                if not item.get("item_name"):
                    continue
                if norm(item["item_name"]) in lookup or norm(item["item_name"]) in {"합계", "총계", "total"}:
                    continue
                item["original_item_name"] = item["item_name"]
                item["raw_fields"] = dict(item)
                result["items"].append(item)
    if result.get("tax_amount"):
        tax = re.fullmatch(r"([\d,]+(?:\.\d+)?)\s*원?\s*\(([\d.]+)\s*%\)", str(result["tax_amount"]))
        if tax:
            result["tax_amount"] = tax[1]
            result.setdefault("tax_rate", tax[2])
    return result


def font_name(custom=None):
    name = "QuoteFlowKorean"
    if name not in pdfmetrics.getRegisteredFontNames():
        path = custom or ROOT / "app" / "fonts" / "NanumGothic-Regular.ttf"
        pdfmetrics.registerFont(TTFont(name, str(path)))
    return name


def make_pdf(title, lines, custom_font=None):
    output = io.BytesIO()
    font = font_name(custom_font)
    style = ParagraphStyle("body", fontName=font, fontSize=9, leading=14, wordWrap="CJK")
    parts = [Paragraph(escape(title), ParagraphStyle("title", parent=style, fontSize=16, leading=23)), Spacer(1, 14)]
    for line in lines:
        # Keep long JSON and user strings breakable and escape ReportLab markup.
        for start in range(0, len(str(line)), 1500):
            parts.append(Paragraph(escape(str(line)[start:start+1500]) or " ", style))
            parts.append(Spacer(1, 5))
    SimpleDocTemplate(output, title=title, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36).build(parts, onFirstPage=page_number, onLaterPages=page_number)
    return output.getvalue()


def quote_pdf(quote, custom_font=None):
    output = io.BytesIO()
    font = font_name(custom_font)
    style = ParagraphStyle("body", fontName=font, fontSize=9, leading=13, wordWrap="CJK")
    p = lambda value: Paragraph(escape(str(value if value is not None else "미기재")), style)
    title_style = ParagraphStyle("title", parent=style, fontSize=18, leading=25)
    parts = [Paragraph("견적서 초안" if quote["kind"] == "draft" else "견적 아카이브 사본", title_style), Spacer(1, 14)]
    for key, label in [("quote_number", "견적번호"), ("title", "제목"), ("issuer_company", "발행회사"), ("customer_name", "고객사"), ("issue_date", "작성일"), ("valid_until", "유효기간"), ("delivery_date", "납기일")]:
        parts.append(p(f"{label}: {quote.get(key) or '미기재'}"))
    parts.append(Spacer(1, 14))
    keys = ["item_name", "specification", "unit", "quantity", "unit_price", "amount"]
    rows = [[p(x) for x in ["품목명", "규격", "단위", "수량", "단가", "금액"]]]
    for item in quote.get("items", []):
        rows.append([p(display_number(item.get(k)) if k in ("quantity", "unit_price", "amount") else item.get(k)) for k in keys])
    table = Table(rows, colWidths=[100, 145, 35, 55, 85, 100], repeatRows=1, splitInRow=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef8")), ("GRID", (0, 0), (-1, -1), .3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    parts += [table, Spacer(1, 14)]
    for key, label in EXPORT_LABELS.items():
        value = quote.get(key)
        if key in ("subtotal", "tax_rate", "tax_amount", "total_amount"):
            value = display_number(value)
        parts.append(p(f"{label}: {value if value is not None else '미기재'}"))
    parts += [Spacer(1, 10), p(f"상태: {STATUS_LABELS[quote['status']]} / 버전: {quote['version']} / 담당자 원본 대조 필요")]
    SimpleDocTemplate(output, leftMargin=22, rightMargin=22, topMargin=30, bottomMargin=30).build(parts, onFirstPage=page_number, onLaterPages=page_number)
    return output.getvalue()


def quote_xlsx(quote):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "견적서"
    rows = [["견적서 초안" if quote["kind"] == "draft" else "견적 아카이브 사본"], ["상태", STATUS_LABELS[quote["status"]]], ["버전", quote["version"]]]
    for key in ("quote_number", "title", "issuer_company", "customer_name", "issue_date", "valid_until", "delivery_date", "currency"):
        label = {"quote_number": "견적번호", "title": "제목", "issuer_company": "발행 회사", "customer_name": "고객사", "issue_date": "작성일", "valid_until": "유효기간", "delivery_date": "납기일", "currency": "통화"}[key]
        rows.append([label, quote.get(key)])
    rows += [[], ["품목명", "규격", "단위", "수량", "단가", "금액"]]
    rows += [[item.get(k) for k in ("item_name", "specification", "unit", "quantity", "unit_price", "amount")] for item in quote.get("items", [])]
    rows.append([])
    for key, label in EXPORT_LABELS.items():
        if key != "currency":
            rows.append([label, quote.get(key)])
    rows.append(["안내", "금액은 정밀도 보존용 문자열입니다. 담당자 검토 후 사용하세요."])
    for row in rows:
        sheet.append(row)
    for row in sheet:
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"  # Never execute user-supplied spreadsheet formulas.
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for col in "ABCDEF":
        sheet.column_dimensions[col].width = 24 if col in "AB" else 18
    sheet["A1"].font = Font(size=16, bold=True)
    sheet["A1"].fill = PatternFill("solid", fgColor="E8EEF8")
    sheet.freeze_panes = "A14"
    sheet.print_options.horizontalCentered = True
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def agent_input(title, data, custom_font=None):
    return make_pdf(title, json.dumps(data, ensure_ascii=False, indent=2, default=str).splitlines(), custom_font)


EXPORT_LABELS = {"currency": "통화", "subtotal": "공급가액", "tax_rate": "세율 (%)", "tax_terms": "세금 조건", "tax_amount": "부가세", "total_amount": "총액", "payment_terms": "결제 조건", "delivery_terms": "납품 조건", "discount_terms": "할인 조건", "notes": "비고"}
STATUS_LABELS = {"review_required": "확인 필요", "extracting": "추출 중", "confirmed": "검토 완료", "rejected": "반려", "archived": "보관"}


def display_number(value):
    if value is None:
        return "미기재"
    text = format(Decimal(str(value)), ",f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def page_number(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(document.pagesize[0]-document.rightMargin, 14, str(document.page))
    canvas.restoreState()
