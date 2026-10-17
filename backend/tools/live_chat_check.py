"""Run two real Solar chat turns using a synthetic quotation, never user files."""
import argparse
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.config import ROOT, Settings
from app.main import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call Solar twice; consumes API usage")
    parser.add_argument("--model", help="Select the initial model")
    parser.add_argument("--switch-model", help="Switch the chat to this model before the second question")
    args = parser.parse_args()
    if not args.live:
        parser.error("Use --live to explicitly enable real API calls")
    folder = ROOT / ".runtime/live-chat-check"
    folder.mkdir(parents=True, exist_ok=True)
    config = Settings(data_dir=folder, database_url="", api_token="", app_env="local", extraction_provider="local")
    book = Workbook()
    for row in [["견적번호", "CHAT-SYNTHETIC-001"], ["고객사", "가상제조사"], ["통화", "KRW"],
                ["작성일", "2026-10-17"], ["유효기간", "견적일로부터 7일"], ["납기", "발주 후 4주"],
                ["공급가액", 250000], ["세액", 25000], ["총액", 275000], ["세금조건", "VAT 별도"],
                ["품목명", "규격", "단위", "수량", "단가", "금액"], ["가상 센서", "TEST-100", "EA", 10, 25000, 250000]]:
        book.active.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    book.close()
    report = []
    with TestClient(create_app(config)) as client:
        generated = []
        original_complete = client.app.state.chat.client.complete

        def capture(*arguments):
            result = original_complete(*arguments)
            generated.append(result[0].model_dump())
            return result

        client.app.state.chat.client.complete = capture
        uploaded = client.post("/api/add", files={"file": ("synthetic-chat.xlsx", buffer.getvalue())})
        uploaded.raise_for_status()
        quote_id = uploaded.json()["quote_id"]
        extracted = client.post("/api/extract", json={"quote_id": quote_id, "provider": "local", "force": True})
        extracted.raise_for_status()
        assert client.get("/api/jobs/" + extracted.json()["job_id"]).json()["status"] == "completed"
        created = client.post("/api/chats", json={"quote_ids": [quote_id], "title": "가상 견적 대화 실검증", "model": args.model})
        created.raise_for_status()
        chat = created.json()
        for index, question in enumerate(("견적금액과 세금 포함 여부를 설명해 주세요.", "그 견적의 납기와 유효기간도 알려주세요.")):
            if index == 1 and args.switch_model:
                switched = client.patch(f"/api/chats/{chat['chat_id']}", json={"model": args.switch_model, "expected_version": chat["version"]})
                switched.raise_for_status()
                chat = switched.json()
            print("Requesting Solar answer...", flush=True)
            response = client.post(f"/api/chats/{chat['chat_id']}/messages", json={"content": question, "expected_version": chat["version"]})
            if not response.is_success:
                print(response.text, flush=True)
                (folder / "diagnostic.json").write_text(json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8")
            response.raise_for_status()
            result = response.json()
            assert result["assistant_message"]["sources"]
            chat = result["chat"]
            report.append(result)
            metadata = result["assistant_message"]["metadata"]
            assert metadata["requested_model"] == chat["model"]
            assert chat["usage"]["complete"] is True
            assert chat["usage"]["total_tokens"] == sum(turn["assistant_message"]["metadata"]["usage"]["total_tokens"] for turn in report)
            print(json.dumps({"requested_model": metadata["requested_model"], "model": metadata["model"],
                              "answer": result["assistant_message"]["content"], "usage": metadata["usage"],
                              "chat_usage": chat["usage"]}, ensure_ascii=False), flush=True)
        assert client.get(f"/api/chats/{chat['chat_id']}/messages").json()["total"] == 4
    (folder / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Two chat turns completed. Report: {folder / 'report.json'}", flush=True)


if __name__ == "__main__":
    main()
