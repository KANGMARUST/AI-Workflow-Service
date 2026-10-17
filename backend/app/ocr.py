"""OCR only the PDF pages that need it, using the existing Upstage key."""
import io
import re

import httpx
from pypdf import PdfReader, PdfWriter

from .documents import DocumentError


class OCRClient:
    def __init__(self, config, transport=None):
        self.config, self.transport = config, transport

    def extract_pages(self, data, page_indices):
        key = self.config.upstage_api_key.get_secret_value()
        if not self.config.ocr_enabled:
            raise DocumentError("스캔 PDF를 처리하려면 OCR_ENABLED=true로 설정하세요.")
        if not key or key.startswith("replace-"):
            raise DocumentError("스캔 PDF의 OCR 처리에는 UPSTAGE_API_KEY가 필요합니다.")
        reader = PdfReader(io.BytesIO(data))
        results = {}
        character_count = 0
        with httpx.Client(base_url=self.config.ocr_base_url.rstrip("/") + "/",
                          headers={"Authorization": f"Bearer {key}"},
                          timeout=self.config.ocr_timeout_seconds, transport=self.transport) as client:
            for index in page_indices:
                writer = PdfWriter()
                writer.add_page(reader.pages[index])
                output = io.BytesIO()
                writer.write(output)
                try:
                    response = client.post("document-digitization", data={"model": "ocr"},
                                           files={"document": ("ocr-page.pdf", output.getvalue(), "application/pdf")})
                    if not response.is_success:
                        raise DocumentError(f"OCR 요청이 거절되었습니다 (HTTP {response.status_code}). 인증·호출 한도를 확인하세요.")
                    payload = response.json()
                    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
                        raise DocumentError("OCR 응답에 올바른 텍스트가 없습니다.")
                    text = payload["text"].strip()
                    character_count += len(text)
                    if character_count > 300000:
                        raise DocumentError("OCR 텍스트가 300,000자를 초과합니다.")
                    results[index] = {"text": text, "page": index + 1,
                                      "model": payload.get("modelVersion"),
                                      "confidence": payload.get("confidence"),
                                      "billed_pages": payload.get("numBilledPages")}
                except httpx.TimeoutException as exc:
                    raise DocumentError("OCR 요청 제한 시간을 초과했습니다. 다시 시도하세요.") from exc
                except (httpx.HTTPError, ValueError) as exc:
                    if isinstance(exc, DocumentError):
                        raise
                    raise DocumentError("OCR 통신 또는 응답 오류입니다. 네트워크·설정을 확인하세요.") from exc
        return results


def has_text(text):
    return bool(re.search(r"[가-힣A-Za-z0-9一-龥]", text))
