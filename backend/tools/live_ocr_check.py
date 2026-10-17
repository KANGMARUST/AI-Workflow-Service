"""Check OCR and optional Studio extraction with a synthetic image-only PDF."""
import argparse
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.config import ROOT, Settings
from app.main import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call real OCR; consumes API usage")
    parser.add_argument("--agent", action="store_true", help="Also call the real Studio extraction agent")
    args = parser.parse_args()
    if not args.live:
        parser.error("Use --live to enable real API calls")
    folder = ROOT / ".runtime/live-ocr-check"
    folder.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1654, 2339), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(ROOT / "app/fonts/NanumGothic-Regular.ttf"), 40)
    lines = ["견적서", "견적번호: OCR-SYNTHETIC-001", "고객사: 가상제조사", "공급사: 가상공급사",
             "통화: KRW", "공급가액: 250000", "부가세: 25000", "총액: 275000",
             "납기: 발주 후 7일", "유효기간: 견적일로부터 30일"]
    for index, line in enumerate(lines):
        draw.text((100, 140 + index * 100), line, font=font, fill="black")
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(595, 842))
    pdf.drawImage(ImageReader(image), 0, 0, 595, 842)
    pdf.save()
    data = output.getvalue()
    assert not PdfReader(io.BytesIO(data)).pages[0].extract_text().strip()
    (folder / "synthetic-scan.pdf").write_bytes(data)
    config = Settings(data_dir=folder, database_url="", api_token="", app_env="local")
    with TestClient(create_app(config)) as client:
        response = client.post("/api/add", files={"file": ("synthetic-scan.pdf", data)})
        response.raise_for_status()
        identifier = response.json()["quote_id"]
        print("Requesting OCR" + (" and Studio extraction..." if args.agent else " and local extraction..."), flush=True)
        response = client.post("/api/extraction-jobs", json={"quote_id": identifier, "provider": "upstage" if args.agent else "local", "force": True})
        response.raise_for_status()
        job = client.get("/api/jobs/" + response.json()["job_id"]).json()
        if job["status"] != "completed":
            raise RuntimeError(job["error"])
        result = client.get("/api/extract", params={"quote_id": identifier}).json()
        assert result["ocr"]["applied"] and "275000" in result["source_text"].replace(",", "")
        assert result["extracted_fields"]["total_amount"] == "275000", result["extracted_fields"]
        assert result["extracted_fields"]["delivery_period"] and result["extracted_fields"]["validity_terms"]
        (folder / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "passed", "provider": result["provider"], "ocr": result["ocr"],
                          "total_amount": result["extracted_fields"]["total_amount"],
                          "delivery_period": result["extracted_fields"]["delivery_period"],
                          "validity_terms": result["extracted_fields"]["validity_terms"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
