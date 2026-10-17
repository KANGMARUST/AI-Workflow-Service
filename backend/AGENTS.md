# 백엔드 Codex 작업 지침

## 담당 범위와 협업

- 이 파일은 `backend/` 하위 작업에 적용한다. 이 대화의 사용자 담당은 백엔드다.
- 작업 범위는 `backend/`다. `frontend/` 파일은 수정하지 않는다. 화면 연동에 필요한 사항은 백엔드 API 계약 문서로 전달한다.
- 자동으로 커밋하지 않는다. 사용자가 명시적으로 요청할 때만 커밋한다.
- 다른 담당자의 변경을 덮어쓰거나 되돌리지 않는다. 작업 전에 관련 파일과 Git 변경 상태를 확인한다.
- 기획과 API 계약은 루트 `README.md`, `docs/README.md`, 관련 `docs/` 문서를 참고하고 실제 코드와 차이가 있으면 구분해 설명한다.
- 현재 프로젝트 구조와 연동 차이는 `PROJECT_CONTEXT.md`, 로컬 환경 명령은 `DEVELOPMENT.md`를 참고한다. 실제 코드가 바뀌면 문서의 현재 상태도 함께 확인한다.

## 서비스 목적과 현재 상태

QuoteFlow는 견적서에서 거래처·담당자·연락처·품목·금액·조건을 추출해 검색하고 검토·관리하는 서비스다.

- 현재 백엔드는 원본 보관, SQLite 영속 저장, XLS/XLSX/텍스트 PDF 추출, Studio 작업 호출, 검색·수정·이력·휴지통·비교·견적 사본 출력을 구현했다. 현 계약과 검증 한계는 `README.md`를 기준으로 한다.
- Upstage 추출·비교 에이전트의 실연결은 가상 PDF로 검증했다. PostgreSQL/Supabase 연결 코드는 있으나 실제 외부 DB 적용과 Docker 실행은 미검증이다.
- 현재 입력 지원은 `.xls`, `.xlsx`, 텍스트 PDF와 스캔 PDF다. 스캔 PDF는 기존 Upstage 키로 OCR을 먼저 적용한다. `.docx`, JPG/PNG 직접 업로드는 확장 범위다.
- 목표 처리 흐름은 업로드·원본 보관 → 표·텍스트 추출 → Upstage 항목 분류 → 표준화 → 정합성 검사 → 담당자 검토·확정 저장이다.

초안 생성 및 AI 초안 제안 기능은 사용자 요청으로 제거했다. 다시 추가하지 않는다. 기존 DB 기록은 보존한다.

## 파일 구조

| 경로 | 역할 |
|---|---|
| `app/main.py` | FastAPI 앱, CORS, 라우터 등록, 헬스 체크 |
| `app/routes.py` | 견적 등록·추출·검색·목록·수정·상태 API |
| `app/schemas.py` | 요청·응답 모델, 품목·견적·상태 타입 |
| `app/config.py` | 환경변수와 설정 로딩 |
| `app/database.py`, `app/repository.py` | DB 모델, 원자적 저장, 버전·이력 |
| `app/service.py`, `app/upstage.py` | 백그라운드 작업과 Studio API |
| `app/chat.py`, `app/chat_client.py`, `app/chat_routes.py`, `app/chat_schemas.py` | 견적 기반 대화·Solar 호출·근거·이력 API |
| `app/chat_usage.py` | 저장된 대화 답변의 입력·출력·전체 토큰 및 모델별 집계 |
| `app/documents.py`, `app/extraction.py`, `app/domain.py` | 파일 처리·출력·정규화·금액 검사·비교 |
| `supabase/schema.sql` | 빈 PostgreSQL용 초기 DDL. 이전 초안의 업그레이드 migration이 아님 |
| `.env.example` | 환경변수 예시 |
| `requirements.txt` | Python 의존성 |
| `Dockerfile`, `docker-compose.yml` | 컨테이너 실행 설정 |

## 실행과 확인

Codex 로컬 개발은 `DEVELOPMENT.md`를 따른다. Python 3.12 가상환경은 `backend/.venv/`에 만들고, 실행할 때 해당 Python 경로를 명시한다. 개발 의존성은 `requirements-dev.txt`에 있다.

저장소 루트의 PowerShell 기준:

```powershell
# 최초 한 번: 기존 .env가 있으면 덮어쓰지 않는다.
Copy-Item backend/.env.example backend/.env
# .env에 필요한 로컬 설정을 입력한 뒤 실행한다.
docker compose -f backend/docker-compose.yml up --build
```

- API 문서: `http://localhost:8000/docs`
- 헬스 체크: `GET http://localhost:8000/health` (`/api/health`가 아니다.)
- Docker는 Python 3.12를 사용한다. 직접 실행할 때는 `backend/`에서 의존성을 설치하고 `python -m uvicorn app.main:app --reload --port 8000`을 실행한다. `.env`는 `backend/` 절대 경로 기준으로 읽는다.
- 주요 환경변수: `APP_ENV`, `API_PREFIX`, `DATABASE_URL`, `DATA_DIR`, `UPSTAGE_API_KEY`, `CORS_ORIGINS`, `API_TOKEN`. `.env`는 `backend/` 절대 경로 기준으로 읽는다.

## API 계약

기본 접두사는 `/api`이며 `API_PREFIX`로 설정한다.

| 메서드 | 경로 | 현재 용도 |
|---|---|---|
| POST | `/api/add` | multipart `file`로 파일 등록 |
| GET | `/api/extract?quote_id=...` | 추출 결과 조회 |
| POST | `/api/search` | 구조화된 조건 검색 |
| GET | `/api/search` | 필수 `keyword`로 키워드 검색 |
| GET | `/api/cards` | 목록 조회 |
| PATCH | `/api/edit/{quote_id}` | 견적서 부분 수정 |
| GET / POST | `/api/status/{quote_id}` | 상태 조회·변경 |

- 목록 응답은 `items`, `total`, `limit`, `offset`을 유지한다. 현재 페이지 크기는 기본 20, 최대 100이고 `offset`은 0 이상이다.
- 상태 값은 `review_required`, `extracting`, `confirmed`, `rejected`, `archived`다. extracting은 작업 API만 설정하고 추출 중 수정·상태 변경·삭제는 충돌로 처리한다. 그 외 추가 상태 전이 제한은 없다.
- 추출 시작은 부작용이 있으므로 구현 시 `POST /api/extract` 또는 `POST /api/extraction-jobs`를 검토한다. 기존 GET 계약을 임의로 제거하거나 처리 시작 용도로 바꾸지 않는다.
- 상세·원본·중복 검사·복원 가능한 휴지통·휴지통 항목별 영구 삭제·공유 Bearer 토큰은 구현됐다. 조직별 로그인·행별 권한은 구현하지 않았다. 현재 범위와 확장 기능을 구분한다.
- API 경로·필드·타입·상태 값 변경 시 프론트엔드 영향과 호환성을 확인하고 필요한 계약 문서 변경을 함께 제시한다.

## 데이터와 구현 원칙

- 원문과 표준화 값을 함께 보관하고, 불명확한 값은 추측으로 채우지 않는다. 누락·추출 실패·검토 필요 사항을 구분한다.
- 금액·수량은 `Decimal`로 계산한다. 현재 DB JSON과 API에는 정밀도 보존용 십진 문자열을 저장한다. 향후 검색용 SQL numeric 컬럼을 추가해도 부동소수점 변환으로 원문 값을 손상시키지 않는다.
- `quotes`와 `quote_items`의 일대다 관계를 유지한다. 견적과 품목을 함께 저장·수정할 때 부분 저장 실패를 고려한다.
- API의 `quote_id`와 DB의 `quotes.id`, `original_item_name`과 DB의 `item_name_original`처럼 이름이 다른 필드는 명시적으로 매핑한다.
- PATCH에서는 필드 미전달과 명시적인 `null`을 구분한다.
- 업로드 구현 시 파일 형식·크기·파일명과 저장 경로를 검증하고, 원본 접근 권한을 고려한다.
- 비밀키와 `.env` 내용을 코드·응답·로그·커밋에 노출하지 않는다. 실제 견적서 개인정보는 익명화해서 검증에 사용한다.
- `schema.sql`은 빈 DB용 초기 DDL이며 RLS를 활성화하고 익명 정책은 만들지 않는다. 실제 DB에는 적용하지 않았다. DB 스키마 변경은 기존 데이터와 권한 영향을 확인하고 별도 migration으로 수행한다.
- 현재 구조에 맞춰 필요한 만큼 구현한다. 요청과 무관한 대규모 재구성이나 추측에 근거한 추상화는 피한다.

## 검증과 작업 보고

- 변경에 맞는 검증을 수행한다. API 구현 시 정상 요청, 입력 오류, 존재하지 않는 ID, 외부 연동 실패 등 관련 동작을 확인한다.
- 외부 키가 없으면 가능한 로컬 검증을 진행하고 실제 연동 검증 여부를 구분한다.
- 문서만 수정했다면 코드 테스트를 불필요하게 추가하지 않는다.
- 작업 완료 시 변경 내용, 수행한 검증, 남은 미구현 또는 검증하지 못한 범위를 간결하게 설명한다. 실행하지 않은 테스트를 통과했다고 쓰지 않는다.
