import io
from datetime import datetime

import pytest
import xlwt

from app.documents import DocumentError, local_extract, read_document
from app.domain import diagnostics
from app.extraction import normalize_result
from app.quote_layout import pdf_line_items
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.documents import make_pdf


def xls_bytes(extra_sheets=0, oversized=False):
    book = xlwt.Workbook()
    hidden = book.add_sheet("Internal")
    hidden.visibility = 1
    hidden.write(0, 0, "not quotation data")
    sheet = book.add_sheet("Quotation")
    rows = [["受信", "가상고객"], ["發行日字", datetime(2026, 10, 16)],
            ["통화", "KRW"], ["총액", "선택"],
            ["品名", "數量", "單位", "단가", "공급가"],
            ["DESCRIPTION", "EA", "UNIT", "UNIT", "AMOUNT"],
            ["상품 A", 1, "EA", 500, 500], ["상품 B", 0, "EA", 200, 0],
            ["비고", "1번 2번중 선택 옵션"]]
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            sheet.write(r, c, value, xlwt.easyxf(num_format_str="YYYY-MM-DD") if isinstance(value, datetime) else xlwt.Style.default_style)
    if oversized:
        sheet.write(10000, 11, "large")
    for i in range(extra_sheets):
        book.add_sheet(f"Sheet{i}")
    output = io.BytesIO()
    book.save(output)
    return output.getvalue()


def test_xls_visible_cells_dates_zero_bilingual_headers_and_options():
    document = read_document(xls_bytes(), ".xls")
    assert "not quotation data" not in document["text"]
    assert "2026-10-16" in document["text"]
    assert len(document["tables"]) == 1
    fields, _ = normalize_result(local_extract(document))
    assert fields["customer_name"] == "가상고객"
    assert fields["issue_date"] == "2026-10-16"
    assert len(fields["items"]) == 2
    assert [(i["quantity"], i["unit_price"], i["amount"]) for i in fields["items"]] == [("1", "500", "500"), ("0", "200", "0")]
    assert fields["total_amount"] is None
    validation = diagnostics(fields)
    assert validation["computed_subtotal"] is None
    assert any(w["code"] == "option_selection_required" for w in validation["warnings"])


@pytest.mark.parametrize("data", [b"fake", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1broken"])
def test_xls_invalid_content(data):
    with pytest.raises(DocumentError):
        read_document(data, ".xls")


@pytest.mark.parametrize("options", [{"extra_sheets": 29}, {"oversized": True}])
def test_xls_size_guards(options):
    with pytest.raises(DocumentError):
        read_document(xls_bytes(**options), ".xls")


def test_pdf_summary_components_and_specs_are_not_double_counted():
    pages = ["품명 수량 단위 단가 금액\n1 장비 세트 4 식 100 400\n2 작업 1 식 50 50\n합 계 450",
             "品名 數量 單位 單價 金額\n1 장비 세트 4 식 100 400\n장치 2 EA 40 80\n-. RAM 16GB\n케이블 1 EA 20 20\n2 작업 1 식 50 50\n설치 1 식 50 50\n- 이 하 여 백 -"]
    rows = pdf_line_items(pages)
    assert len(rows) == 5
    assert rows[0]["raw_fields"]["line_type"] == "group"
    assert rows[0]["raw_fields"]["repeated_on_pages"] == [2]
    component = next(i for i in rows if i["item_name"] == "장치")
    assert component["specification"] == "-. RAM 16GB"
    assert component["raw_fields"]["parent_item_name"] == "장비 세트"
    fields, _ = normalize_result({"items": rows, "subtotal": "450"})
    validation = diagnostics(fields)
    assert validation["computed_subtotal"] == "450"
    assert not any(w["code"] == "subtotal_mismatch" for w in validation["warnings"])
    assert any(w["code"] == "hierarchical_items" for w in validation["warnings"])


def test_pdf_missing_quantity_does_not_silently_remove_a_row():
    assert pdf_line_items(["품명 수량 단위 단가 금액\n1 제품 1 EA 20 20\n2 다른 제품 EA 30 30"]) == []


def test_xls_upload_extract_and_original_download(tmp_path):
    data = xls_bytes()
    with TestClient(create_app(Settings(_env_file=None, data_dir=tmp_path, extraction_provider="local"))) as client:
        assert ".xls" in client.get("/api/capabilities").json()["supported_extensions"]
        response = client.post("/api/add", files={"file": ("quotation.xls", data)})
        assert response.status_code == 201
        identifier = response.json()["quote_id"]
        response = client.post("/api/extract", json={"quote_id": identifier, "provider": "local"})
        assert response.status_code == 202
        assert client.get("/api/jobs/"+response.json()["job_id"]).json()["status"] == "completed"
        quote = client.get("/api/quotes/"+identifier).json()
        assert quote["item_count"] == 2 and quote["items"][1]["quantity"] == "0"
        assert client.get(f"/api/quotes/{identifier}/source").content == data


def test_pdf_agent_result_is_reconciled_with_explicit_rows(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, upstage_api_key="test-only-key"))
    content = make_pdf("Synthetic quotation", ["품명 수량 단위 단가 금액", "1 제품 A 2 EA 100 200", "합 계 200"])
    with TestClient(app) as client:
        app.state.service.agent.run = lambda *args: {"data": {"items": [{"item_name": "misaligned row", "quantity": "99"}], "subtotal": "200"}}
        identifier = client.post("/api/add", files={"file": ("sample.pdf", content)}).json()["quote_id"]
        response = client.post("/api/extract", json={"quote_id": identifier, "provider": "upstage"})
        job = client.get("/api/jobs/"+response.json()["job_id"]).json()
        assert job["status"] == "completed", job
        quote = client.get("/api/quotes/"+identifier).json()
        assert quote["item_count"] == 1
        assert quote["items"][0]["quantity"] == "2"
        assert quote["items"][0]["amount"] == "200"
        assert quote["items"][0]["raw_fields"]["source_page"] == 1
