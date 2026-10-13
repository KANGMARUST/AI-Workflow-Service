# 견적 아카이브 AI - 프로토타입 개발 명세

작성일: 2026-10-13 (Asia/Seoul)
상태: 프로토타입 구현 완료. 최초 명세를 기준으로 에이전트 개발을 실행했고 실제 자료·통합 테스트·브라우저 확인 결과로 최종 갱신했다.
기획서: https://app.notion.com/p/3f827af47d0e802e9c04d6a9dc6c68e0

## 1. 사용자 요청 및 개발 범위

이 문서를 먼저 작성하고 이 문서를 읽은 개발 에이전트가 구현한다. 사용자는 프로토타입에서 기획서의 기능을 모두 요구했으므로 MVP와 확장 기능을 함께 구현한다. 로컬 실행 가능한 제품을 제공하고 외부 배포는 하지 않는다. 기존 HR/장사비서 프로젝트는 변경하지 않는다.

사용자는 고객에게 견적을 발행하는 제조·납품업체 담당자다. 업로드 → 자동 추출 → 오류 검토·수정 → 확정 저장 → 검색·비교 → 재사용 → 새 견적 출력의 전체 흐름을 지원한다. 수정 버전, 수주 상태, 자연어 검색, 통계를 포함한다. 수주 상태는 사람이 입력하며 견적금액을 매출로 표시하지 않는다.

## 2. 참조 자료 및 주의할 구조

사용자가 말한 data는 현재 D:/workflow AI hacker/Input_data에서 찾은 PDF 2개와 XLS 1개다. 프로젝트 data/에 원본을 복사하여 로컬에서만 참조한다. 공개 저장소·원격 AI로 자동 전송하지 않는다.

- 단일 페이지 PDF: 품목 3개, 공급가액 16,000,000원, VAT 별도. 줄 단위 텍스트를 활용해야 표 추출에서 누락되지 않는다.
- 두 페이지 PDF: 주 견적 5개 패키지의 합계 266,740,000원. 두 번째 페이지에는 같은 패키지와 세부 품목이 반복된다. 패키지 행은 합산하고 세부 행은 parent_index로 연결해 이중 합산하지 않는다. 사양 줄은 해당 품목의 specification에 연결한다.
- XLS: COVER 시트의 3품목과 한자 헤더를 읽는다. 2번·3번은 서로 선택하는 옵션이며 합계가 숫자 대신 '선택'으로 기재되어 있다. 기본 품목만 합산하고 두 옵션은 미선택 상태로 보존한다. 담당자가 정확히 하나를 선택해야 확정한다. 숨겨진 WData 시트의 시간 숫자는 견적 데이터로 해석하지 않는다.

## 3. 구조와 실행

project/
- frontend/: React + Vite, 한국어 웹 UI. Node 24, npm 11 계열. VITE_API_BASE 환경변수.
- backend/: Python FastAPI, 지속 저장(기본 SQLite), 파일 보관, 추출/검증/검색/출력. DATABASE_URL 설정 시 PostgreSQL/Supabase 접속을 지원하거나 연결 설정·SQL을 제공하며 검증 여부를 명시한다.
- data/: 사용자 견적 원본. gitignore 대상.
- tests/: 통합 테스트 및 검증 결과. 실제 자료는 로컬에서만 사용.
- DEVELOPMENT.md: 명세와 구현 결과의 단일 기준.
- README.md, .env.example, start.ps1: 설치·실행 안내.

외부 키 없이 모든 기본 업무 흐름을 사용할 수 있어야 한다. 로컬 구조 분석과 로컬 OCR로 실제 파일을 처리한다. 선택적으로 OpenAI 호환 API의 AI 구조화/자연어 분석 연결을 제공한다. 키가 없으면 로컬 분석으로 동작한다고 명확히 표시하며 AI 실행으로 가장하지 않는다. 원격 전송은 운영자가 EXTERNAL_AI_ENABLED와 키를 명시 설정했을 때만 허용한다. .env에 민감 키를 작성하거나 기존 키 파일 내용을 출력하지 않는다.

## 4. 데이터 계약

Quote JSON:
id, number, customer, issuer, contact, phone, email, issue_date(YYYY-MM-DD 또는 빈 값), valid_until, delivery, ship_to, payment_terms, project_name, currency(KRW 등), tax_rate(퍼센트), discount(금액), subtotal, tax, total, source_total, status(draft/sent/won/lost), review_status(pending/confirmed), notes, items, warnings, source_url, source_name, source_text, extraction_method, version, parent_id, created_at, updated_at.

Item JSON:
name, specification, unit, quantity, unit_price, amount, is_component(boolean), parent_index(integer|null), original_text, included(boolean, 기본 true), option_group(string, 기본 빈값). 선택 옵션은 included=false로 시작하고 동일 option_group에서 정확히 하나를 선택해야 확정된다. 수량/단가/금액의 빈 값은 null. 금액 계산은 Decimal와 통화 자릿수를 사용한다. package/components의 이중 합산과 선택하지 않은 옵션의 합산을 금지한다. 할인은 헤더 금액 할인, 세금은 할인 후 공급가액 기준이다. source_total은 원본과 검증에 사용하고 시스템 계산 total과 구분한다.

Warnings: 문자열 배열. 필수 누락, 음수, 금액 불일치, 원본 합계 불일치, 품목 없음, 중복 파일 등을 표시한다. 확정에는 거래처·날짜·품목·수량·단가 등 필수 값과 금액 검증을 충족해야 한다. acknowledged_warnings(boolean, 기본 false)는 원본 합계 차이·세율 가정 등 확인 가능한 경고를 담당자가 명시적으로 인정할 때 사용한다. 필수 누락·음수·품목 산술 오류는 인정으로 우회할 수 없다. 세금율이 원본에 없을 때 기본 추정임을 표시하고 사용자가 확인한다.

실제 PDF는 시각적으로 연락처를 가렸지만 내부 텍스트에 기존 연락처가 남은 사례를 확인했다. PDF 연락처는 시각 결과와 일치 여부를 확인하거나 비워 검토 대상으로 표시하며, source_text에 숨겨진 개인 연락처가 그대로 노출되지 않도록 마스킹한다. 사용자 원본 파일은 수정하지 않는다.

## 5. API 계약 (프론트/백 공유)

모든 응답은 JSON, 오류는 detail 문자열. 프론트는 /api 기반 상대경로를 Vite proxy로 사용하거나 VITE_API_BASE를 사용한다.

- GET /api/health → {ok, extraction_mode, ocr_available, database}
- GET /api/quotes?query=&customer=&item=&date_from=&date_to=&min_amount=&max_amount=&status=&review_status= → Quote[]
- GET /api/quotes/{id} → Quote
- POST /api/quotes (Quote 부분 JSON) → 새 수동 초안 Quote
- POST /api/upload (multipart files 복수) → {quotes: Quote[], errors: [{filename,detail}]}; XLSX/XLS/PDF/DOCX/PNG/JPG 지원
- POST /api/import-samples → {quotes: Quote[], errors: []}; 실제 data 파일을 로컬 등록, 중복 업로드는 기존 Quote 반환
- PUT /api/quotes/{id} (수정 Quote) → Quote; 검증·합계 재계산, 버전 스냅샷 저장
- POST /api/quotes/{id}/confirm → Quote
- PATCH /api/quotes/{id}/status {status} → Quote
- POST /api/quotes/{id}/copy → Quote; 신규 번호/날짜, 검토 pending, parent_id 연결, 원본 파일은 참고 링크 유지
- GET /api/quotes/{id}/history → [{version, changed_at, snapshot: Quote}]
- GET /api/compare?query= → [{quote_id,number,customer,issue_date,currency,name,specification,unit,quantity,unit_price,amount,delivery,payment_terms,is_component}]; confirmed만 기본 대상
- POST /api/natural-search {question} → {answer, quotes: Quote[], filters: object}; 로컬 조건 해석, 근거 없는 데이터 생성 금지
- GET /api/stats → {quote_count,confirmed_count,pending_count,quoted_amount,status_counts,monthly:[{month,count,amount}],customers:[{customer,count,amount}]}; 매출과 견적금액 구분
- GET /api/templates → [{id,name,description}]; 기본 standard/compact + 추가 사용자 템플릿
- POST /api/templates (multipart file + name) → 템플릿; XLSX {{customer}}, {{number}}, {{issue_date}}, {{total}} 등 placeholder 및 items 시트 규칙 안내
- GET /api/quotes/{id}/export?format=xlsx|pdf&template=standard → 실제 파일; confirmed만 출력. 한국어 폰트와 전체 품목/조건/총액 포함
- GET /api/files/{filename} → 원본; 파일명 경로 순회 차단

별칭 /api/add,/api/extract,/api/search,/api/cards,/api/edit,/api/status는 적합한 HTTP 동사로 제공할 수 있다. 변경 작업은 GET으로 처리하지 않는다.

## 6. UI 구성과 디자인

한국어, 밝은 배경과 짙은 남색 사이드바, 청록색 강조. 견적 데이터 관리에 필요한 명확한 표와 충분한 여백. 아이콘은 작은 SVG 또는 lucide-react. 불필요한 이미지/장식 없이 제품에 집중한다. 데스크톱/모바일 대응, 키보드 접근과 레이블 제공.

- 대시보드: 견적 건수, 검토 필요, 확정 견적금액, 담당자 입력 수주 현황, 월별 및 거래처별 현황.
- 견적 보관함: 다중 업로드/드래그, 실제 샘플 불러오기, 수동 새 견적, 검색·필터, 검토/진행 상태, 원본 보기.
- 상세/검토: 원본 PDF/이미지 또는 다운로드와 추출 텍스트, 헤더 입력, 품목 행 추가/삭제/사양/부품 토글, 오류 표시, 저장/확정, 상태 변경, 새 견적으로 복사, 출력, 버전 이력 비교.
- 단가 비교: 동일/유사 품목 검색, 거래처·일자·규격·수량·통화·단위·단가·조건을 표로 표시. 다른 조건을 자동 동일 취급하지 않는다.
- 자연어 검색: 질문, 해석 조건과 근거 견적을 표시. 원격 AI 사용 여부 명시.
- 양식 관리: standard/compact 선택, 사용자 XLSX 템플릿 등록 및 규칙 안내.

## 7. 에이전트 분담

프론트 에이전트는 frontend/만 변경. 백엔드 에이전트는 backend/만 변경. 검증 에이전트는 tests/ 및 검증 자료를 담당하고 통합 결함을 보고한다. 메인 에이전트가 API 계약, 통합, 문서/스크립트, 실자료 검증과 브라우저 시연을 담당한다. 명세 변경은 서로 공유한다. 모호하거나 결정해야 하는 사항은 상위 에이전트에 질문하고 독립 작업을 진행한다. Git push/외부 배포는 수행하지 않는다.

## 8. 완료 기준 및 검증 계획

- 실 PDF 2개 + XLS 등록, PDF 첫 문서 3행/16,000,000 공급가액, 복합 문서 5개 패키지/266,740,000 공급가액과 세부 항목 연결을 검증한다.
- XLSX/DOCX/이미지 입력을 별도 합성 fixture로 검증한다. OCR은 실제 로컬 엔진으로 실행한다.
- 중복 파일/부분 업로드 실패/빈 값/0/음수/소수점/할인/세금/틀린 합계/패키지 중복에 대한 유효성 검증.
- 저장 후 앱 재시작에도 유지, 확정 전 출력 차단, 수정 시 재검토, 버전 이력 보존.
- 검색/날짜·가격 필터/자연어 질문/조건별 비교/수동 수주 현황/템플릿 선택 및 XLSX 업로드.
- 복사 후 수량 수정 → 확인/확정 → Excel·PDF 파일의 값 검증. PDF 한국어/페이지 넘김/전체 품목을 렌더로 검토.
- 프론트 production build, API 테스트 및 브라우저 실제 업무 흐름 검증.
- README에 설치/환경/실행/제약을 기록하고 이 MD의 기능별 상태·테스트 결과·남은 제한을 최종 갱신한다.

## 9. 구현 현황 (완료 시 갱신)

| 기능 | 상태 | 검증 |
|---|---|---|
| 파일 등록·원본·자동 추출 | 완료 | 실제 PDF 2개/XLS 1개, 합성 XLSX/DOCX/PNG, 부분 업로드 실패·중복 등록 검증 |
| 검토·수정·확정·지속 저장 | 완료 | 누락·음수·불일치·선택 옵션 차단, 확인 인정, SQLite 재시작 유지 검증 |
| 검색·필터·단가 비교 | 완료 | 거래처/품목/날짜/금액/상태 필터 및 비교의 규격·단위·통화·수량 보존 |
| 견적 재사용·금액 계산·출력 | 완료 | 복사 후 수량 변경, Decimal 할인·세금 계산, Excel/PDF 내부값 검증 |
| 버전 이력·진행 상태 | 완료 | 스냅샷 보관, 한국어 필드·품목별 변경 비교, 담당자 상태 입력 |
| 자연어 검색·통계 | 완료 | 업무 조건 로컬 해석, 견적 통계, 외화 금액의 원화 합계 혼입 방지 |
| 다양한 파일·출력 양식 | 완료 | 한국어 로컬 OCR, 표준/간결/사용자 XLSX 및 PDF 변환, 80품목 5페이지 출력 |
| 브라우저 시연·실행 안내 | 완료 | 실자료 등록·확정·복사·수량 수정·상태·검색, production build와 start.ps1 실행 확인 |

## 10. 최종 검증 결과 및 제한

### 실제 구현

- 프론트: React 19 + Vite 6, API 프록시, 데스크톱/모바일 대응 한국어 화면. Windows 실제 Node 24.21.0/npm 11.19.0 환경에서 설치·빌드 성공.
- 백엔드: FastAPI + SQLAlchemy, 기본 SQLite 지속 저장. DATABASE_URL로 PostgreSQL/Supabase 직접 연결을 선택한다. 파일과 템플릿은 로컬 보관한다.
- 문서 분석: pdfplumber/xlrd/openpyxl/python-docx 구조 추출. 스캔 PDF·이미지는 RapidOCR + 동봉 한국어 PP-OCRv4 ONNX 모델을 로컬 실행한다. 모델 출처와 라이선스는 backend/models/README.md에 기록했다. 구조 추출은 로컬 규칙 기반이며 외부 AI 실행으로 가장하지 않는다.
- 실제 XLS 선택 옵션을 위한 included/option_group, 부품 포함과 상위패키지 관계, 원본 총액의 subtotal/total 구분, blocking_warnings를 최종 계약에 추가했다.
- 견적 복사는 source_total을 초기화하고 원본 참고 링크와 parent_id는 유지한다. 수정은 재검토 상태로 돌아가며 이전 스냅샷을 보존한다.
- 통계는 모든 통화의 건수를 표시하되 원화금액은 KRW 확정 견적만 집계한다. currency_totals/foreign_currency_count로 외화는 별도로 관리한다. 실제 매출은 추정하지 않는다.
- 사용자 양식은 XLSX placeholder와 items 시트를 사용한다. 사용자 PDF는 워크북 셀·표 내용과 거래조건·계산 결과를 보존하는 변환이며 이미지·차트·정밀 인쇄 배치는 재현하지 않는다.

### 테스트와 시각 검증

최종 tests/integration-results.json: **12개 실행, 실패 0, 오류 0**. 격리 DB와 별도 서버를 사용하며 외부 AI를 비활성화했다.

1. 실제 원본 3개와 중복 등록, PDF 3행/16,000,000원 공급가액, 복합 PDF 5패키지+15세부품목/266,740,000원 공급가액.
2. XLS의 대체 옵션 미선택/다중 선택 차단 및 선택 후 합계, 숨김 연락처 마스킹.
3. XLSX·DOCX·한국어 이미지 OCR의 실제 품목·규격·수량·단가·금액, 부분 업로드 실패.
4. 검토 전 출력 차단, 필수 누락·음수·산술 오류와 경고 인정.
5. 과거 견적 복사 후 수량 4→8 변경, 버전 이력, 실제 Excel/PDF의 값.
6. 소수/0/할인/세금/패키지 계산과 잘못된 포함 관계 차단.
7. 검색·비교·날짜/금액/상태 필터·자연어 조건·수주 현황.
8. 표준과 간결 PDF의 실제 차이, 사용자 XLSX/PDF 제목·placeholder·품목·금액 보존.
9. 파일 경로 순회 차단, 서버 재시작 후 DB 유지.
10. 80품목 5페이지 PDF의 전체 품목·거래조건·총액 보존, 첫/마지막 페이지 PNG 시각 확인.
11. USD 견적을 추가해도 KRW 통계 불변, 외화 건수와 통화별 금액 분리.
12. 클라이언트 confirmed 위조/음수 변경/경고 인정으로 검토·출력 차단을 우회할 수 없음.

프론트 `npm run build` 성공. 실 브라우저에서 원본 3개 등록, 검토 확인·확정, 새 견적 복사, 수량 변경(공급가액 31,200,000원/총액 34,320,000원), 상태 변경, 날짜·품목 자연어 검색을 확인했다. preview의 시연 데이터는 원본 3개와 복사 1개를 남겼다. 한국어 버전 비교·유효기간 상대 표현 표시도 개선했다.

### 실행 및 남은 제한

- 로컬 앱: http://127.0.0.1:5173, API: http://127.0.0.1:8000. setup.ps1/start.ps1/stop.ps1 및 README 실행 안내 제공. start.ps1로 두 서버 기동과 HTTP 준비 상태를 확인했다.
- 실제 Supabase/PostgreSQL·외부 AI 접속은 자격증명이 없어 미검증. 연결 설정, 서버측 선택 AI 연동 코드, PostgreSQL SQL과 Docker 구성은 제공했다. Docker 실행은 현재 환경에 Docker가 없어 미검증.
- 자연어 검색은 날짜·거래처·품목·금액·상태 조건의 로컬 해석이며 범용 질의응답·단가 예측은 지원하지 않는다.
- 임의 회사 문서, 손글씨·저해상도 사진 등은 추출 오류가 있을 수 있어 원본과 담당자 검토가 필수다. 제공된 자료와 명시한 테스트 형식에 대해 검증했다.
- 운영 로그인·조직권한은 구현 범위에 포함하지 않은 로컬 프로토타입이다. 원본 자료는 gitignore로 제외하고 자동 원격 전송하지 않는다.
