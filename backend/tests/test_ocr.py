import io

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.config import Settings
from app.documents import DocumentError, read_document
from app.main import create_app
from app.ocr import OCRClient


def scanned_pdf(mixed=False, header=False):
    """A real image-only page, optionally following a native-text page."""
    image = Image.new("RGB", (800, 1000), "white")
    ImageDraw.Draw(image).text((30, 50), "Synthetic quote: TOTAL 275000", fill="black")
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(400, 500))
    if mixed:
        pdf.drawString(20, 470, "Native text page")
        pdf.showPage()
    pdf.drawImage(ImageReader(image), 0, 0, 400, 500)
    if header:
        pdf.drawString(20, 480, "Header")
    pdf.save()
    return output.getvalue()


def ocr_client(handler, **settings):
    return OCRClient(Settings(_env_file=None, upstage_api_key="synthetic-key", **settings),
                     transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("mixed,header", [(False, False), (True, False), (False, True)])
def test_ocr_only_scanned_pages_preserves_page_order(mixed, header):
    calls = []

    def handler(request):
        assert request.url.path == "/v1/document-digitization"
        assert request.headers["authorization"] == "Bearer synthetic-key"
        assert b'name="model"\r\n\r\nocr' in request.content
        calls.append(request)
        return httpx.Response(200, json={"text": "총액: 275000\n납기: 발주 후 7일", "modelVersion": "ocr-test", "numBilledPages": 1})

    data = scanned_pdf(mixed, header)
    assert PdfReader(io.BytesIO(data)).pages[-1].extract_text().strip() == ("Header" if header else "")
    document = read_document(data, ".pdf", ocr=ocr_client(handler))
    assert len(calls) == 1
    assert "총액: 275000" in document["text"]
    assert document["ocr"]["pages"][0]["page"] == (2 if mixed else 1)
    if mixed:
        assert document["text"].index("Native text page") < document["text"].index("총액")


def test_text_pdf_does_not_call_ocr():
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(20, 800, "Native quote TOTAL 275000")
    pdf.save()

    def unexpected(request):
        pytest.fail("Native text PDF must not call OCR")

    document = read_document(output.getvalue(), ".pdf", ocr=ocr_client(unexpected))
    assert document["ocr"]["applied"] is False


@pytest.mark.parametrize("payload", [{}, {"text": None}, [], {"text": 123}])
def test_invalid_ocr_response(payload):
    with pytest.raises(DocumentError, match="텍스트"):
        read_document(scanned_pdf(), ".pdf", ocr=ocr_client(lambda _: httpx.Response(200, json=payload)))


@pytest.mark.parametrize("status", [401, 429, 500])
def test_ocr_http_error_is_sanitized(status):
    with pytest.raises(DocumentError, match=f"HTTP {status}") as error:
        read_document(scanned_pdf(), ".pdf", ocr=ocr_client(lambda _: httpx.Response(status, text="secret provider body")))
    assert "secret" not in str(error.value)


def test_ocr_timeout_and_empty_result():
    def timeout(request):
        raise httpx.ReadTimeout("secret", request=request)

    with pytest.raises(DocumentError, match="제한 시간"):
        read_document(scanned_pdf(), ".pdf", ocr=ocr_client(timeout))
    with pytest.raises(DocumentError, match="읽을 수 있는 텍스트"):
        read_document(scanned_pdf(), ".pdf", ocr=ocr_client(lambda _: httpx.Response(200, json={"text": ""})))


@pytest.mark.parametrize("options,match", [({"ocr_enabled": False}, "OCR_ENABLED"), ({"upstage_api_key": ""}, "UPSTAGE_API_KEY")])
def test_missing_ocr_configuration(options, match):
    client = OCRClient(Settings(_env_file=None, **options))
    with pytest.raises(DocumentError, match=match):
        read_document(scanned_pdf(), ".pdf", ocr=client)


@pytest.mark.parametrize("provider", ["local", "upstage"])
def test_scanned_upload_ocr_precedes_agent_and_is_saved(tmp_path, provider):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, upstage_api_key="synthetic-key"))
    original = scanned_pdf()
    order = []

    def ocr_handler(request):
        order.append("ocr")
        return httpx.Response(200, json={"text": "견적번호: OCR-TEST\n총액: 275000\n납기: 발주 후 7일\n유효기간: 30일", "numBilledPages": 1})

    with TestClient(app) as client:
        app.state.service.ocr.transport = httpx.MockTransport(ocr_handler)

        def agent_run(pdf, *args):
            order.append("agent")
            assert pdf != original
            text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
            assert "OCR-TEST" in text and "275000" in text and "발주 후 7일" in text
            return {"data": {"quote_number": "OCR-TEST", "total_amount": "275000"}}

        app.state.service.agent.run = agent_run
        quote_id = client.post("/api/add", files={"file": ("scan.pdf", original)}).json()["quote_id"]
        response = client.post("/api/extraction-jobs", json={"quote_id": quote_id, "provider": provider})
        job = client.get("/api/jobs/" + response.json()["job_id"]).json()
        assert job["status"] == "completed", job
        result = client.get("/api/extract", params={"quote_id": quote_id}).json()
        assert result["ocr"]["applied"] is True
        assert result["extracted_fields"]["total_amount"] == "275000"
        assert "OCR-TEST" in result["source_text"]
        assert client.get(f"/api/quotes/{quote_id}/source").content == original
        assert order == (["ocr", "agent"] if provider == "upstage" else ["ocr"])


def test_ocr_failure_marks_job_failed_without_agent_call(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, upstage_api_key="synthetic-key"))
    with TestClient(app) as client:
        app.state.service.ocr.transport = httpx.MockTransport(lambda _: httpx.Response(503))
        app.state.service.agent.run = lambda *args: pytest.fail("OCR failed: agent must not run")
        quote_id = client.post("/api/add", files={"file": ("scan.pdf", scanned_pdf())}).json()["quote_id"]
        response = client.post("/api/extraction-jobs", json={"quote_id": quote_id, "provider": "upstage"})
        job = client.get("/api/jobs/" + response.json()["job_id"]).json()
        assert job["status"] == "failed" and "OCR" in job["error"]
        assert client.get("/api/quotes/" + quote_id).json()["extraction_status"] == "failed"
