"""Keep source structure alongside normalized quote fields; never infer missing values."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re

VERSION = 1


def value(raw):
    if isinstance(raw, (date, datetime)):
        return raw.isoformat()
    if raw is None or isinstance(raw, (str, int, float, bool)):
        return raw
    return str(raw)


def extra_fields(text):
    result = []
    seen = set()
    labels = r'사업자등록번호|등록번호|공급사|공급자|회사명|주소|소재지|업태|종목|보증기간|보증조건|보증|운송조건|인도조건|배송조건|배송비|설치조건|설치범위|제외사항|특기사항|특이사항|비고|납기|납품장소|결제조건|지불조건|유효기간|통화|팩스|FAX'
    for line_number, line in enumerate(text.splitlines(), 1):
        # A line may contain several explicitly labelled conditions.
        matches = list(re.finditer(r'([^:/\n]{1,40}?)\s*[:：]\s*([^/\n]+)', line))
        if not matches:
            match = re.match(r'^\s*(' + labels + r')\s+(.+)$', line, re.I)
            matches = [match] if match else []
        for match in matches:
            label, content = (part.strip() for part in match.groups())
            if not label or not content or (label, content) in seen:
                continue
            seen.add((label, content))
            result.append(dict(label=label, value=content, source_line=line_number, original_text=line.strip()))
    return result


def capture(path, fallback_text='', pdf_pages=None):
    """Capture all sheets/paragraphs/pages without modifying normalized quote values."""
    from extraction import sanitize_pdf, ocr
    suffix = path.suffix.lower()
    content = dict(version=VERSION, format=suffix.lstrip('.'), pages=[], sheets=[], blocks=[], limitations=[])
    parts = []
    if suffix == '.pdf':
        if pdf_pages is None:
            import pdfplumber
            pdf_pages = []
            with pdfplumber.open(path) as book:
                for index, page in enumerate(book.pages, 1):
                    text = page.extract_text() or ''
                    method = 'text'
                    if len(text.strip()) < 30:
                        text = ocr(page.to_image(resolution=180).original)
                        method = 'ocr'
                    pdf_pages.append(pdf_page(page, index, text, method))
        content['pages'] = pdf_pages
        parts = [page['text'] for page in pdf_pages]
        content['limitations'] = ['PDF의 숨김 연락처·대표자 정보는 원본 화면에서 확인해 보완합니다.', '이미지·도장·정확한 서식은 보존된 원본 파일에서 확인합니다.']
    elif suffix == '.xlsx':
        from openpyxl import load_workbook
        formulas = load_workbook(path, data_only=False)
        cached = load_workbook(path, data_only=True)
        for sheet in formulas:
            cells = []
            cached_sheet = cached[sheet.title]
            text_lines = []
            for row in sheet:
                texts = []
                for cell in row:
                    if cell.value is None and cell.comment is None:
                        continue
                    formula = cell.value if cell.data_type == 'f' else None
                    raw = cached_sheet[cell.coordinate].value if formula else cell.value
                    cells.append(dict(address=cell.coordinate, row=cell.row, column=cell.column,
                                      value=value(raw), formula=formula, number_format=cell.number_format,
                                      comment=cell.comment.text if cell.comment else '',
                                      hyperlink=cell.hyperlink.target if cell.hyperlink else '',
                                      row_hidden=bool(sheet.row_dimensions[cell.row].hidden),
                                      column_hidden=bool(sheet.column_dimensions[cell.column_letter].hidden)))
                    texts.append(f'{cell.coordinate}: {raw if raw is not None else ""}' + (f' [수식 {formula}]' if formula else '') + (f' [메모 {cell.comment.text}]' if cell.comment else ''))
                if texts:
                    text_lines.append(' | '.join(texts))
            content['sheets'].append(dict(name=sheet.title, state=sheet.sheet_state,
                rows=sheet.max_row, columns=sheet.max_column, merged_cells=[str(area) for area in sheet.merged_cells.ranges], cells=cells))
            parts.extend(['시트: ' + sheet.title, *text_lines])
        formulas.close(); cached.close()
        content['limitations'] = ['수식은 원문 그대로 보존하며 재계산하지 않습니다. 계산 결과는 파일에 저장된 값만 표시합니다.']
    elif suffix == '.xls':
        import xlrd
        book = xlrd.open_workbook(path, formatting_info=True)
        for sheet in book.sheets():
            cells = []
            lines = []
            for r in range(sheet.nrows):
                texts = []
                for col in range(sheet.ncols):
                    cell = sheet.cell(r, col)
                    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        continue
                    raw = cell.value
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        try: raw = xlrd.xldate_as_datetime(raw, book.datemode).isoformat()
                        except (ValueError, OverflowError): pass
                    note = getattr(sheet, 'cell_note_map', {}).get((r, col))
                    address = xlrd.formula.colname(col) + str(r + 1)
                    cells.append(dict(address=address, row=r+1, column=col+1, value=value(raw),
                        comment=note.text if note else '', formula=None,
                        row_hidden=bool(getattr(sheet.rowinfo_map.get(r), 'hidden', False)),
                        column_hidden=bool(getattr(sheet.colinfo_map.get(col), 'hidden', False))))
                    texts.append(f'{address}: {raw}' + (f' [메모 {note.text}]' if note else ''))
                if texts: lines.append(' | '.join(texts))
            content['sheets'].append(dict(name=sheet.name, state='hidden' if sheet.visibility else 'visible', rows=sheet.nrows,
                columns=sheet.ncols, merged_cells=[list(area) for area in sheet.merged_cells], cells=cells))
            parts.extend(['시트: ' + sheet.name, *lines])
        content['limitations'] = ['XLS의 수식 표현식·도형은 원본 파일에 보존합니다. 데이터베이스에는 저장된 셀 값을 기록합니다.']
    elif suffix == '.docx':
        from docx import Document
        from docx.text.paragraph import Paragraph
        from docx.table import Table
        doc = Document(path)
        def blocks(parent, location):
            element = parent.element.body if location == 'body' else parent._element
            for index, child in enumerate(element.iterchildren(), 1):
                if child.tag.endswith('}p'):
                    text = Paragraph(child, parent).text
                    content['blocks'].append(dict(kind='paragraph', location=location, index=index, text=text))
                    parts.append(text)
                elif child.tag.endswith('}tbl'):
                    table = Table(child, parent)
                    rows = [[cell.text for cell in row.cells] for row in table.rows]
                    content['blocks'].append(dict(kind='table', location=location, index=index, rows=rows))
                    parts.extend(' | '.join(row) for row in rows)
        blocks(doc, 'body')
        for index, section in enumerate(doc.sections, 1):
            blocks(section.header, f'header-{index}')
            blocks(section.footer, f'footer-{index}')
        content['limitations'] = ['도장·그림·주석·각주 등 문서 객체와 정확한 서식은 원본 파일에서 확인합니다.']
    else:
        content['pages'] = [dict(number=1, text=fallback_text, method='ocr', tables=[])]
        parts = [fallback_text]
        content['limitations'] = ['이미지의 텍스트는 OCR 결과이며 원본과 대조해야 합니다.']
    text = '\n'.join(parts)
    content['text'] = text
    # Extraction labels use the human-readable original, not cell coordinates.
    label_text = fallback_text or text
    return dict(document_content=content, document_content_version=VERSION,
                extra_fields=extra_fields(label_text), original_extra_fields=extra_fields(label_text))


def pdf_page(page, index, text, method):
    from extraction import sanitize_pdf
    warnings = []
    tables = []
    try:
        tables = [[[sanitize_pdf(cell) if cell else '' for cell in row] for row in table] for table in page.extract_tables()]
    except Exception as error:
        warnings.append('표 구조를 인식하지 못했습니다. 원문 및 원본 파일에서 확인해주세요. (' + type(error).__name__ + ')')
    return dict(number=index, text=sanitize_pdf(text), method=method, tables=tables,
                width=page.width, height=page.height, warnings=warnings)
