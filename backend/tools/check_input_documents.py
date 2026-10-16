"""Check quotation files without modifying originals or the application's DB.

Default: local file parsing only. --live uploads the specified documents to
Upstage using the configured extraction agent and consumes API usage.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import ROOT, Settings
from app.documents import read_document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT.parent / "docs/input-data")
    parser.add_argument("--live", action="store_true", help="Send the quotation files to Upstage and test the full API flow")
    args = parser.parse_args()
    files = sorted(p for p in args.input_dir.iterdir() if p.is_file() and p.suffix.lower() in {".xls", ".xlsx", ".pdf"} and not p.name.startswith("~$"))
    if not files:
        parser.error("No XLS, XLSX or PDF quotation files found")
    output = ROOT / ".runtime/input-document-check"
    output.mkdir(parents=True, exist_ok=True)
    report = []
    for path in files:
        document = read_document(path.read_bytes(), path.suffix.lower())
        report.append({"filename": path.name, "text_characters": len(document["text"]), "table_count": len(document["tables"]),
                       "verified_line_rows": len(document["line_items"]), "selection_required": document["selection_required"], "warnings": document["warnings"]})
    if args.live:
        from fastapi.testclient import TestClient
        from app.main import create_app
        config = Settings(data_dir=output, database_url="", api_token="", agent_timeout_seconds=240)
        with TestClient(create_app(config)) as client:
            for path, row in zip(files, report):
                print(f"Extracting {path.name}...", flush=True)
                response = client.post("/api/add", files={"file": (path.name, path.read_bytes())})
                response.raise_for_status()
                identifier = response.json()["quote_id"]
                response = client.post("/api/extraction-jobs", json={"quote_id": identifier, "provider": "upstage", "force": True})
                response.raise_for_status()
                job = client.get("/api/jobs/" + response.json()["job_id"]).json()
                quote = client.get("/api/quotes/" + identifier).json()
                extraction = client.get("/api/extract", params={"quote_id": identifier}).json()
                (output / (path.stem + ".json")).write_text(json.dumps({"job": job, "quote": quote, "extraction": extraction}, ensure_ascii=False, indent=2), encoding="utf-8")
                row.update(status=job["status"], error=job["error"], quote_id=identifier, item_count=quote["item_count"], issue_date=quote["issue_date"],
                           subtotal=quote["subtotal"], total_amount=quote["total_amount"], computed_subtotal=quote["validation"]["computed_subtotal"],
                           warning_codes=sorted({w["code"] for w in quote["validation"]["warnings"]}))
                print(json.dumps({k: row[k] for k in ("filename", "status", "item_count", "subtotal", "total_amount")}, ensure_ascii=False), flush=True)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Checked {len(report)} documents. Report: {output / 'report.json'}", flush=True)
    if args.live and any(row["status"] != "completed" or row["item_count"] == 0 for row in report):
        raise SystemExit("Some extractions failed or returned no line items; inspect report.json")


if __name__ == "__main__":
    main()
