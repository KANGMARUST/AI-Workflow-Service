# QuoteFlow 백엔드

FastAPI 기반 견적 아카이브 API. 루트 `backend/`만 사용하며 `project/`는 사용하지 않는다. 프론트 없이 Swagger 또는 HTTP 요청으로 전체 흐름을 실행할 수 있다.

기능별 동작, 전체 API, 데이터 필드, 프론트 연결 순서와 구현 한계는 [백엔드 기능 상세 안내](FEATURES.md)를 참고한다.

## 실행

저장소 루트의 PowerShell:

```powershell
uv venv --python 3.12 backend/.venv
uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements-dev.txt
# .env가 없을 때만 생성. 기존 키를 덮어쓰지 않는다.
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
backend/.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

- Swagger: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json
- Health: http://127.0.0.1:8000/health
- 프론트 연결 상태: `GET /api/capabilities`
- 기본 DB: `backend/.runtime/quotes.db`, 원본: `backend/.runtime/files/`
- DB와 파일은 서버를 재시작해도 보존된다. 둘을 함께 백업한다.

**현재 작업 실행기는 프로세스 내부 BackgroundTasks다. Uvicorn worker는 1개로 실행한다.** 재시작 중 미완료 작업은 실패 처리되며 사용자가 재시도한다. 여러 서버/worker가 같은 DB를 공유하는 운영 배포에는 외부 작업 큐와 worker 소유권 처리가 추가로 필요하다.

Docker:

```powershell
docker compose -f backend/docker-compose.yml up --build
```

한글 폰트와 라이선스는 `app/fonts/`에 포함되어 있다. Docker named volume에 DB·원본을 보존한다. 이 환경에서는 Docker 실행 파일이 확인되지 않아 이미지 빌드·실행은 검증하지 않았다.

## 환경변수

설정은 실행 디렉터리와 관계없이 `backend/.env`와 프로세스 환경변수에서 읽는다. 비밀값은 응답에 반환하지 않는다.

| 변수 | 의미 |
|---|---|
| `DATA_DIR` | DB·원본 저장 디렉터리. 기본 `backend/.runtime` |
| `DATABASE_URL` | 비우면 SQLite. Supabase는 PostgreSQL 직접 연결/세션 pooler URL 사용 |
| `AUTO_CREATE_SCHEMA` | 외부 PostgreSQL 자동 테이블 생성 여부. 기본 false |
| `UPSTAGE_API_KEY` | Studio API 키. `.env`에만 저장 |
| `EXTRACTION_PROVIDER` | auto / local / upstage. auto는 키가 있으면 Studio, 없으면 로컬 |
| `QUOTE_EXTRACT_AGENT_ID`, `QUOTE_EXTRACT_CONFIG_ID` | 추출 에이전트·설정 버전 |
| `QUOTE_COMPARE_AGENT_ID`, `QUOTE_COMPARE_CONFIG_ID` | 비교 에이전트·설정 버전 |
| `AGENT_TIMEOUT_SECONDS` | 외부 작업 제한 시간. 기본 180초 |
| `CORS_ORIGINS` | 쉼표로 구분한 프론트 주소. 기본 localhost/127.0.0.1:5173 |
| `API_TOKEN` | 선택적 공유 Bearer 토큰. `APP_ENV=production`에서는 필수 |
| `MAX_UPLOAD_MB`, `MAX_DOCUMENT_PAGES` | 기본 20MB, 100페이지 |

`SUPABASE_URL`과 `SUPABASE_KEY`는 이전 골격의 호환 설정으로 남아 있지만 DB 연결에는 사용하지 않는다. 현재 구현은 SQLAlchemy + PostgreSQL 드라이버를 사용한다. HTTPS REST URL 대신 `DATABASE_URL=postgresql+psycopg://...`를 설정한다. 비밀번호는 URL 인코딩한다.

`supabase/schema.sql`은 **빈 DB용 새 초기 스키마**다. 이전 SQL 초안과 구조가 다르며, 기존 테이블에 적용할 업그레이드 migration이 아니다. 이미 이전 스키마로 DB를 만들었다면 별도 DB/스키마에 설치하거나 데이터 보존 migration을 먼저 작성한다. 이 작업에서 외부 DB에는 어떤 DDL도 적용하지 않았다.

SQL에는 RLS 활성화가 포함되며 익명 정책은 만들지 않는다. 서버는 필요한 권한이 있는 신뢰된 DB 역할로 연결한다. 이 API는 하나의 팀/워크스페이스용이며 사용자별 로그인·조직별 데이터 격리는 구현하지 않았다. 공개 배포 시 공유 토큰이 사용자별 권한을 대체하지는 않는다.

## 프론트 담당자 연결 순서

기존 `/add`, `/extract`, `/search`, `/cards`, `/edit/{quote_id}`, `/status/{quote_id}` 경로는 유지했다. 등록 직후 자동으로 추출하지 않는다. 상세·작업·원본·비교 API가 추가됐다. 루트 `docs/api-contract.md`는 초기 초안이므로 **현재 계약은 이 문서와 실행 중인 OpenAPI를 따른다.**

| 순서 | 요청 | 결과 |
|---|---|---|
| 1 | `POST /api/add` multipart `file` | `quote_id`, `status`, `duplicate`와 상세. HTTP 201 |
| 2 | `POST /api/extraction-jobs` | `{quote_id, provider:"auto"}` → 작업 ID. HTTP 202 |
| 3 | `GET /api/jobs/{job_id}` | queued / running / completed / failed, `result`, `error` |
| 4 | `GET /api/quotes/{quote_id}` | 헤더·품목·검토 오류·버전 |
| 5 | `PATCH /api/edit/{quote_id}` | 변경 필드와 `expected_version` 전송 |
| 6 | `POST /api/status/{quote_id}` | 검토 후 상태·메모 저장 |
| 7 | `GET /api/cards` 또는 `POST /api/search` | 목록 `{items,total,limit,offset}` |
| 8 | `GET /api/items/history?keyword=센서` (keyword 생략 시 전체) | 품목별 단가·거래조건 이력 |
| 9 | `POST /api/compare` | 선택한 견적의 조건별 단가 비교 |
| 10 | `GET /api/quotes/{quote_id}/export?format=xlsx` | 지정 양식 파일. pdf도 지원 |

### 업로드와 추출

```javascript
const form = new FormData();
form.append("file", selectedFile);
form.append("direction", "received"); // sent: 보낸 견적서, received: 받은 견적서
const uploaded = await fetch(`${API}/api/add`, { method: "POST", body: form, headers: authHeaders }).then(checkResponse);
const job = await fetch(`${API}/api/extraction-jobs`, {
  method: "POST",
  headers: { ...authHeaders, "Content-Type": "application/json" },
  body: JSON.stringify({ quote_id: uploaded.quote_id, provider: "auto" })
}).then(checkResponse);
// 2초 간격 GET /api/jobs/{job.job_id}; completed/failed에서 폴링 종료.
// checkResponse는 !response.ok이면 오류를 표시하고, 성공일 때 response.json() 반환.
```

`API`는 예를 들어 `http://127.0.0.1:8000`. 토큰이 없으면 `authHeaders={}`, 있으면 `{Authorization:"Bearer ..."}`. multipart 요청의 Content-Type은 브라우저가 boundary와 함께 설정하도록 직접 지정하지 않는다.

활성 견적과 업로드 원본이 중복이면 기존 견적을 반환한다. 같은 원본이 휴지통에만 있으면 새 견적으로 등록된다. 복원할 때 같은 원본의 활성 견적이 있으면 HTTP 409다. 재추출은 기존 검토값을 바꾸므로 `{force:true}`를 명시한다. 추출 중에는 해당 견적의 수정·상태 변경·삭제가 HTTP 409다. GET `/api/extract?quote_id=...`는 조회만 하며 외부 호출을 시작하지 않는다.

### 상세·수정·상태

금액·수량·세율은 정확한 **십진 문자열 또는 null**이다. 표시용 숫자 변환과 서버 전송값을 구분한다. `0`은 결측이 아니다. 날짜는 `YYYY-MM-DD` 또는 null이다. 통화 미기재를 KRW로 채우지 않는다.

```json
{
  "expected_version": 3,
  "customer_name": "가상제조사",
  "items": [
    {"item_name":"센서","specification":"TS-100","unit":"개","quantity":"10","unit_price":"25000","amount":"250000","currency":"KRW"}
  ],
  "review_note": "원본과 대조하여 정정"
}
```

PATCH 미전달 필드는 유지하고 명시적인 null은 지운다. `items`를 보내면 전체 품목 배열을 교체하고 `items:null`은 빈 배열로 만든다. 상세 품목의 `item_id`, `line_number`는 읽기 전용이므로 수정 요청에서 제외한다. 내용 수정 시 검토 상태는 `review_required`로 돌아가며 `direction`만 수정하면 기존 검토 상태를 유지한다. 오래된 `expected_version`은 HTTP 409이므로 최신 상세를 다시 읽는다.

### 납기·유효기간·견적금액·보낸/받은 구분

- `direction`: 사용자 선택 라벨. `sent`(보낸 견적서), `received`(받은 견적서), `null`(미분류). 업로드 multipart 또는 PATCH에서 저장한다. AI는 이 값을 추정하거나 재추출로 바꾸지 않는다. 기존 데이터는 미분류로 조회된다.
- 라벨은 기존 DB의 `quotes.payload.direction`에 저장하므로 테이블 변경이나 기존 데이터 migration은 필요 없다. `GET /api/cards?direction=received`, `POST /api/search`의 `direction` 조건으로 필터링한다. 같은 원본의 기존 라벨과 다른 라벨을 지정해 중복 업로드하면 409이며 기존 견적을 PATCH로 수정한다.
- `validity_terms`: “견적일로부터 7일” 같은 유효기간 원문. 확정 날짜가 있으면 `valid_until`에도 저장한다. 상대 기간을 임의의 만료일로 바꾸지 않는다.
- `delivery_period`: “발주 후 4주”, “일정협의” 같은 납기 원문. `delivery_date`는 확정 납기일이며 `delivery_terms`는 납품 장소·인도조건이다.
- 상세·목록의 읽기 전용 `quoted_amount`는 명시된 `total_amount`를 우선하고, 없으면 `subtotal`을 반환한다. 프론트 연동 시 이를 견적금액으로 표시하고 공급가액 사용 여부를 함께 표시해야 한다. VAT 별도 합계를 세금 포함 총액으로 바꾸지 않는다. 옵션 선택형 문서에 숫자 합계가 없으면 금액은 null이다.
- `validity_terms`, `delivery_period`는 수정 및 PDF/XLSX 출력에도 반영한다. 과거 추출 결과에 없는 새 필드는 원본을 재추출해야 저장된다.

프론트엔드는 별도 담당 범위다. 업로드·수정 화면의 `direction` 선택, 목록의 라벨·`quoted_amount` 표시, 상세의 `validity_terms`·`delivery_period` 표시는 프론트 담당자가 위 계약에 맞춰 연결해야 한다.

아카이브의 수량/단가를 수정해도 원문 금액은 자동 변경하지 않는다. 정확한 재계산은 `validation.computed_item_amounts`와 `computed_subtotal`로 별도 제공한다. `validation.warnings`는 `{code,path,message}` 배열이며 누락·중복 가능성·계산 불일치 등을 표시한다. `raw_fields`와 수정 이력, 최초 추출 원문은 보존한다.

`POST /api/status/{id}` 본문 예: `{"status":"confirmed","note":"원본 대조 완료","expected_version":4}`. 상태는 `review_required`, `extracting`, `confirmed`, `rejected`, `archived`. extracting은 시스템 작업 API에서만 설정한다. 그 외 상태 전이를 추가로 제한하지 않으며 담당자 검토 메모를 기록할 수 있다.

새로고침 후에는 `GET /api/extract?quote_id=...`의 `latest_job`으로 작업 폴링을 재개할 수 있다. 이 응답의 `source_text`, `source_fields`는 저장된 추출 원문 및 원문 행 대조가 반영된 결과이고 `extracted_fields`는 현재 수정값이다. `GET /api/quotes/{id}/jobs`는 해당 견적의 작업 이력을 페이지 단위로 반환한다.

원본은 `GET /api/quotes/{id}/source`, 이력은 `GET /api/quotes/{id}/history?limit=20&offset=0`. 인증이 켜졌다면 원본도 fetch로 Authorization 헤더를 넣어 Blob으로 연다.

### 검색·비교

```json
{"keyword":"센서","customer_name":"가상제조사","item_name":"센서","date_from":"2026-01-01","date_to":"2026-12-31","amount_min":"100000","amount_max":"1000000","status":"confirmed","limit":20,"offset":0}
```

POST `/api/search`의 모든 조건은 선택적이다. GET `/api/search`는 keyword가 필수다. `/cards`는 status, kind(신규 등록은 archive, 과거 draft 값은 조회 호환용), limit, offset 필터를 받는다. 상세 검색에는 contact_name, kind도 사용할 수 있다. 기본 limit 20, 최대 100. 검색은 현재 MVP에서 DB의 활성 문서를 읽어 Python의 문자열·Decimal로 필터링한다. 대규모 데이터에는 DB 검색 인덱스·전용 필드로 이전해야 한다.

POST `/api/compare` 본문: `{"quote_ids":["id-a","id-b"],"item_name":"센서"}`. 동일 품목명·규격·단위·통화가 명시된 행만 비교한다. 결과 `pairs`의 차액은 후자-전자, 비율은 전자 단가 기준이며 전자 단가 0이면 null. 수량·날짜·세금·할인·납품·결제조건 차이와 미기재 조건을 함께 보여준다. 다른 규격·통화 또는 정보 부족은 `excluded_rows`에 표시한다. 환율·단위 변환은 추정하지 않는다.

`GET /api/stats`는 문서·검토·거래처·품목 수만 반환한다. 실제 수주율·매출 통계는 생성하지 않는다.

### 저장된 견적 출력

출력은 `GET /api/quotes/{id}/export?format=pdf` 또는 xlsx. 현재 지정 양식은 1개다. Excel은 숫자 정밀도 보존을 위해 금액·수량을 문자열로 저장하며 수식 자동 재계산은 제공하지 않는다. 사용자 입력이 Excel 수식으로 실행되지 않게 저장한다. 원본 미기재 값은 출력에서도 미기재로 표시한다.

### 선택적 Studio 비교 설명

POST `/api/agent-runs`:

```json
{"kind":"compare","quote_ids":["id-a","id-b"]}
```

반환된 작업은 `/api/jobs/{id}`에서 조회한다. 서로 다른 견적 2~5건을 사용한다.

백엔드가 저장된 견적을 PDF로 조립해 Studio에 전달한다. AI 결과는 제안이며 저장·확정·출력을 자동 실행하지 않는다. 비교 결과의 `verified_comparison`은 백엔드가 Decimal로 별도 계산한 결과다. 외부 임시 입력 파일은 작업 후 삭제를 시도하고 `input_file_deleted`로 성공 여부를 남긴다.

### 휴지통과 오류

- DELETE `/api/quotes/{id}`: 복원 가능한 휴지통 이동. 원본·품목·이력은 보존.
- GET `/api/trash`: 휴지통 목록.
- POST `/api/quotes/{id}/restore`: 복원. 같은 원본의 활성 견적이 있으면 409.
- DELETE `/api/trash/{id}`: 휴지통 견적의 DB 기록·작업·수정 이력을 영구 삭제. 원본 파일은 다른 견적이 참조하지 않을 때 삭제.
- HTTP 400: 빈 파일/잘못된 파일명, 401: 인증, 404: 없는 ID/원본, 409: 중복·작업 중·버전 충돌, 413: 파일 크기, 422: 입력/파일/계산 형식 오류, 503: 저장소/필수 외부 설정 오류.
- 작업을 받은 뒤 발생한 외부 오류는 작업의 `status=failed`, `error`에 표시한다. 외부 응답 본문과 키는 전달하지 않는다.

## 검증

```powershell
cd backend
.venv/Scripts/python.exe -m pytest tests -q --basetemp=.runtime/pytest
.venv/Scripts/python.exe -m ruff check app tests tools --select E9,F63,F7,F82,F401
uv pip check --python .venv/Scripts/python.exe
```

초안 기능 제거 후 자동 테스트는 파일 등록·추출·검토·검색·비교·출력, 오류 처리와 제거된 API 차단을 검증한다. 기존 SQLite 데이터는 보존하며 DB 스키마를 파괴적으로 변경하지 않는다. 과거 draft 데이터의 조회 호환을 위해 종류·원본 연결 필드는 남겨두지만 새 초안 생성이나 AI 초안 제안은 제공하지 않는다.

이전 가상 문서 기반 Studio 추출·비교 실연결 기록은 `.runtime/live-agent-check/`에 있다. 이번 제거 작업에서는 외부 API를 다시 호출하지 않는다.

실연결 테스트는 명시적으로 실행한다(가상 PDF 업로드 및 API 사용량 발생):

```powershell
backend/.venv/Scripts/python.exe -u backend/tools/live_agent_check.py --live
# 8000번 API 서버를 먼저 실행한 뒤 전체 HTTP 흐름:
backend/.venv/Scripts/python.exe -u backend/tools/live_agent_check.py --live --api
# XLSX 셀 추출→PDF 조립→Studio 흐름도 검증:
backend/.venv/Scripts/python.exe -u backend/tools/live_agent_check.py --live --api --xlsx
```

Supabase 실DB·Docker 실행, 다양한 기업 실문서 정확도는 미검증이다. 로컬 파서는 명시된 라벨과 품목 표를 처리하는 보조 기능이며 자유 양식의 의미 추출은 Studio 및 담당자 검토가 필요하다. 스캔/OCR·Word·기업별 양식·수주/매출 데이터·조직별 로그인은 확장 범위다.

## 코드 위치

- `app/routes.py`: API, `schemas.py`: 요청·응답 계약
- `app/database.py`, `repository.py`: DB·트랜잭션·이력
- `app/documents.py`, `extraction.py`: 파일 검사·파싱·정규화·출력
- `app/domain.py`: 정합성 검사·비교 Decimal 계산
- `app/service.py`, `upstage.py`: 작업 실행·외부 API
- `agent_configs/`: 실제 Studio 설정 JSON·가상 샘플·사용 가이드
- `supabase/schema.sql`: 빈 PostgreSQL용 초기 DDL, `tools/export_schema.py`: 재생성

외부 호출 방식은 [Upstage Agents API](https://console.upstage.ai/docs/agents)와 [작업 생성 API](https://console.upstage.ai/ko/api/agents/jobs/create-job), [해커톤 가이드북](https://ku-sejong-hackathon-playbook.vercel.app/#sec5)을 따른다.

## 지정 입력 문서 지원

입력은 `.xls`, `.xlsx`, 텍스트 PDF다. 지정된 `docs/input-data/`의 견적 3개에 대한 처리 방식, 선택 옵션·상위/구성품 관계와 검증 결과는 [입력 문서 지원 안내](INPUT_DOCUMENTS.md)에 정리했다. `sample_quotes.csv`, README 및 `~$` 임시 파일은 이 검사 대상에서 제외한다.

```powershell
# 로컬 읽기만 검사: 외부 호출 없음
backend/.venv/Scripts/python.exe -u backend/tools/check_input_documents.py
# 실제 지정 문서를 Studio로 보내 API 흐름 검사: API 사용량 발생
backend/.venv/Scripts/python.exe -u backend/tools/check_input_documents.py --live
```

이 도구는 실제 문서를 읽으므로 실행 범위를 먼저 확인한다. 별도 `.runtime/input-document-check/` DB와 파일에 결과를 저장하고 기본 서비스 DB나 입력 원본을 수정하지 않는다.
