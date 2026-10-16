"""Explicit opt-in smoke test. Uploads only the bundled fictional PDFs to Upstage."""
import argparse
import io
import json
import sys
import time
from pathlib import Path

import httpx
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.extraction import normalize_result
from app.upstage import UpstageClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Authorize the two synthetic-document API calls")
    parser.add_argument("--api", action="store_true", help="Run the full PDF workflow through the local API instead")
    parser.add_argument("--xlsx", action="store_true", help="Use a synthetic XLSX for the local HTTP flow")
    args = parser.parse_args()
    if not args.live:
        parser.error("Use --live to send the bundled fictional PDFs to Upstage")
    samples = Path(__file__).resolve().parents[1] / "agent_configs" / "samples"
    output = settings.data_dir / "live-agent-check"
    output.mkdir(parents=True, exist_ok=True)
    if args.api:
        filename = "quoteflow-live-review.pdf"
        content = (samples/"quote_review.pdf").read_bytes()
        if args.xlsx:
            filename = "quoteflow-live-review.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            for row in [["견적번호", "LIVE-XLSX-DEMO"], ["발행 회사", "가상공급사"], ["고객사", "가상제조사"], ["작성일", "2026-10-16"], ["통화", "KRW"], ["세금 조건", "부가세 별도"], ["세율", "10"], ["공급가액", "500000"], ["부가세", "50000"], ["총액", "550000"], [], ["품목명", "규격", "단위", "수량", "단가", "금액"], ["온도 센서", "TS-100", "개", 10, 25000, 250000], ["제어 모듈", "CM-20", "개", 2, 100000, 190000], ["연결 케이블", "CB-5", "개", None, 10000, 50000]]:
                sheet.append(row)
            buffer = io.BytesIO()
            workbook.save(buffer)
            workbook.close()
            content = buffer.getvalue()
        token = settings.api_token.get_secret_value()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30, headers=headers) as api:
            response = api.post("/api/add", files={"file": (filename, content)})
            response.raise_for_status()
            q = response.json()
            response = api.post("/api/extract", json={"quote_id": q["quote_id"], "provider": "upstage", "force": True})
            response.raise_for_status()
            identifier = response.json()["job_id"]
            print("Local API: extraction queued", flush=True)
            started = time.monotonic()
            while time.monotonic()-started < 240:
                job = api.get("/api/jobs/"+identifier).json()
                if job["status"] in ("completed", "failed"):
                    break
                time.sleep(2)
            assert job["status"] == "completed", job.get("error", "timeout")
            q = api.get("/api/quotes/"+q["quote_id"]).json()
            assert q["items"][2]["quantity"] is None
            comparison = None
            cards = api.get("/api/cards", params={"kind": "archive"}).json()["items"]
            other = next((row for row in cards if row["quote_id"] != q["quote_id"]), None)
            if other:
                response = api.post("/api/compare", json={"quote_ids": [q["quote_id"], other["quote_id"]]})
                response.raise_for_status()
                comparison = response.json()
            for fmt in ("pdf", "xlsx"):
                response = api.get(f"/api/quotes/{q['quote_id']}/export", params={"format": fmt})
                response.raise_for_status()
                (output/f"api-quote.{fmt}").write_bytes(response.content)
            encoded = json.dumps({"quote": q, "comparison": comparison, "job": job}, ensure_ascii=False, indent=2)
            (output/"api-workflow.json").write_text(encoded, encoding="utf-8")
            (output/f"api-workflow-{'xlsx' if args.xlsx else 'pdf'}.json").write_text(encoded, encoding="utf-8")
            print(f"Local HTTP API ({filename}): upload, live extraction and PDF/XLSX export passed.", flush=True)
        return
    client = UpstageClient(settings)
    checks = []
    for kind, filename in (("extract", "quote_review.pdf"), ("compare", "input_comparison.pdf")):
        print(f"Running {kind} with fictional sample...", flush=True)
        result = client.run((samples/filename).read_bytes(), getattr(settings, f"quote_{kind}_agent_id"), getattr(settings, f"quote_{kind}_config_id"))
        (output/f"{kind}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        data = result["data"]
        if kind == "extract":
            fields, warnings = normalize_result(data)
            assert len(fields["items"]) == 3
            assert fields["items"][2]["quantity"] is None
            assert fields["items"][1]["amount"] == "190000"
            assert fields["total_amount"] == "550000"
        elif kind == "compare":
            assert data["comparison_status"] == "conditional"
            assert json.loads(data["excluded_rows_json"])[0]["quote_id"] == "DEMO-C"
        checks.append({"kind": kind, "passed": True, "remote_job_id": result["remote_job_id"], "input_file_deleted": result.get("input_file_deleted")})
        print(f"{kind}: passed; temporary remote file deleted={result.get('input_file_deleted')}", flush=True)
    (output/"summary.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print("All 2 live checks passed.")


if __name__ == "__main__":
    main()
