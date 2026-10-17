# PDF OCR 처리

기존 등록·추출 API 그대로 스캔 PDF를 처리한다. 프론트 변경과 DB 마이그레이션은 필요 없다.

## 처리 순서

1. `POST /api/add`의 `file`로 PDF를 등록한다. 원본 바이트를 보관한다.
2. `POST /api/extraction-jobs`에 `{ "quote_id": "...", "provider": "auto" }`를 보낸다.
3. 텍스트가 없거나 이미지 면적 합계가 페이지 면적의 50% 이상인 페이지를 감지한다. 후자는 작은 머리말 텍스트가 포함된 스캔 문서도 읽기 위한 기준이다.
4. 필요한 페이지만 개별 PDF로 만들어 Upstage OCR에 순서대로 전달한다. 일반 텍스트 페이지는 OCR을 호출하지 않는다. 혼합 PDF의 페이지 순서를 유지한다.
5. OCR을 사용한 경우 인식 텍스트와 일반 페이지 텍스트를 합친 텍스트 PDF를 생성해 Studio 추출 에이전트에 전달한다. 로컬 추출도 같은 OCR 텍스트를 사용한다. OCR을 사용하지 않은 일반 PDF는 기존처럼 원본을 Studio로 보낸다.
6. 인식 텍스트·OCR 메타데이터·경고와 견적 추출 결과를 저장한다. 이후 견적 대화에서도 저장한 원문을 사용한다.

OCR은 `POST /v1/document-digitization`, multipart `model=ocr`, `document=PDF`를 사용한다. 공식 계약: [Upstage Document OCR](https://console.upstage.ai/api/parse/document-ocr).

## 설정

`backend/requirements.txt`에 추가된 `pypdf`를 설치한 뒤 서버를 재시작한다.

| 환경변수 | 기본값 / 설명 |
|---|---|
| `OCR_ENABLED` | `true` |
| `OCR_BASE_URL` | `https://api.upstage.ai/v1` |
| `OCR_TIMEOUT_SECONDS` | `120`, 페이지당 요청 제한 시간 |
| `UPSTAGE_API_KEY` | 기존 Studio/Solar와 같은 키 |

`provider=local`은 의미 분류를 로컬에서 한다는 뜻이다. 스캔 PDF는 이 경우에도 외부 OCR 요청과 API 사용량이 발생한다. 키가 없거나 OCR을 끄면 스캔 페이지 추출 작업이 실패한다. 일반 텍스트 PDF와 Excel은 OCR 키 없이 로컬 추출할 수 있다.

## 응답

- `GET /api/capabilities`에 `ocr: { enabled, configured, provider: "upstage", mode: "scanned_pages" }`를 추가한다. `configured`는 키 설정 여부이며 원격 권한을 검사한 결과는 아니다.
- `GET /api/extract?quote_id=...`는 `source_text`에 OCR을 포함한 원문을 반환하고 다음 메타데이터를 추가한다.

```json
{"ocr":{"applied":true,"pages":[{"page":1,"model":"ocr-...","confidence":0.99,"billed_pages":1}]}}
```

`page`는 원본 PDF의 1부터 시작하는 페이지 번호다. 공급자가 반환하지 않은 `model`, `confidence`, `billed_pages`는 null이다. 기존 추출 기록과 OCR 미사용 문서는 `{ "applied": false, "pages": [] }`를 반환한다. OCR 사용량은 대화 토큰 집계에 합산하지 않는다.

오류는 기존 작업 조회의 `status=failed`, `error`로 확인한다. OCR의 인증·호출 한도·시간 초과·응답 오류가 발생하면 에이전트를 호출하지 않는다. 빈 페이지는 경고를 남기고, 전체 문서에 읽을 수 있는 텍스트가 없으면 실패한다. OCR 후에도 기존 최대 300,000자 제한을 적용한다. 일부 페이지 오류가 있으면 전체 추출을 실패 처리하며 부분 결과를 저장하지 않는다.

이미지 면적 기준은 감지 규칙이므로 작은 이미지 영역의 글자나 손상된 텍스트 레이어를 모두 감지하는 것은 아니다. OCR은 원본 표의 시각적 배치를 그대로 보존하지 않으며 숫자·납기·유효기간은 담당자가 원본과 대조한다.

## 검증

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_ocr.py -q -p no:cacheprovider
# 가상 이미지 전용 PDF로 실제 외부 API 호출: API 사용량 발생
backend/.venv/Scripts/python.exe -u backend/tools/live_ocr_check.py --live --agent
```

실호출 도구는 개인정보 없는 가상 견적만 사용하며 기본 DB와 분리된 `backend/.runtime/live-ocr-check/`에 결과를 저장한다.
