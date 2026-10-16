# 현재 프로젝트 구성

확인일: 2026-10-16. 개발 대상은 루트 `backend/`이며 `project/`는 사용하지 않는다. 프론트엔드 파일은 수정하지 않았다.

## 구현 상태

| 기능 | 현재 상태 |
|---|---|
| 원본 등록 | PDF/XLS/XLSX 형식·크기 검증, 안전한 파일 보관, SHA-256 중복 확인 |
| 영속 저장 | SQLAlchemy, 기본 SQLite. PostgreSQL/Supabase 직접 연결 설정 지원 |
| 추출 | 로컬 표·라벨 파서 및 Studio 에이전트. 별도 POST 작업 시작, GET 결과 조회 |
| 검토 | 원문·표준화 값 보존, 누락·중복 가능성·금액 불일치 표시, 사용자 수정·확정 |
| 검색 | 거래처·담당자·품목·기간·금액·상태, 목록 페이지 처리 |
| 원본·이력 | 상세, 원본 다운로드, 버전 충돌 처리, 수정 스냅샷 이력 |
| 삭제 | 휴지통 이동·조회·복원. 영구 삭제 없음 |
| 단가 비교 | 동일 품목·규격·단위·통화 비교, 조건 차이·비교 제외 이유 표시 |
| 출력 | 한글 PDF·Excel 지정 양식 1개. Excel 금액은 정밀도 보존 문자열 |
| 외부 AI | 추출·비교 Studio 설정과 API 호출. 외부 임시 파일 정리 |
| 인증 | 선택적 공유 Bearer 토큰. production에서는 필수. 조직별 로그인 없음 |
| 통계 | 문서·검토·거래처·품목 수. 매출/수주율 추정 없음 |

현재 API는 `README.md`와 실행 중 `/openapi.json`에 문서화되어 있다. 루트 공용 `docs/`는 최초 골격 문서이며 프론트 계약의 최신 기준으로 사용하지 않는다.

## 주요 파일

```text
backend/
├── app/
│   ├── main.py          # 앱 수명주기·인증·CORS·오류 처리
│   ├── config.py        # backend/.env·환경변수
│   ├── schemas.py       # 요청·응답 모델
│   ├── routes.py        # API
│   ├── database.py      # 견적·품목·이력·작업 테이블
│   ├── repository.py    # 저장·조회·원자적 수정
│   ├── documents.py     # 파일 검사·파싱·PDF/Excel 출력
│   ├── extraction.py    # 외부 결과 정규화·결측 처리
│   ├── domain.py        # Decimal 계산·정합성·비교
│   ├── service.py       # 서비스 흐름·백그라운드 작업
│   ├── upstage.py       # 파일 업로드·작업 실행·폴링·정리
│   └── fonts/           # 한글 폰트·OFL 라이선스
├── tests/test_workflow.py
├── agent_configs/       # 실제 Studio 설정과 가상 샘플
├── tools/               # 초기 SQL·샘플 생성·명시적 실연결 검사
├── supabase/schema.sql  # 빈 외부 DB용 초기 스키마
└── .runtime/            # Git 제외: DB·원본·검증 결과
```

## 검증과 남은 범위

초안 생성·AI 초안 제안 기능은 사용자 요청으로 제거했다. 현재 검증은 자동 테스트와 지정 린트로 수행한다. 이전 실연결 기록은 과거 검증 자료이며 현재 제공 기능과 구분한다.

실제 Supabase 자격증명이 없어 외부 DB 접속·스키마 적용은 검증하지 않았다. Docker 실행 파일이 없어 빌드·실행을 검증하지 않았다. 지정된 견적 3개의 실연결 결과는 `INPUT_DOCUMENTS.md`에 정리했다. 다른 기업 양식과 프론트 UI 연동은 별도 검증 대상이다.

프로세스 내부 작업 실행기는 단일 Uvicorn worker용이다. 다중 worker/서버 배포는 외부 작업 큐가 필요하다. 검색은 MVP의 Python 필터이므로 대규모 데이터에서는 검색용 DB 인덱스/컬럼을 설계해야 한다. 스캔 OCR·Word·조직별 권한·수정본 자동 연결·수주/매출 데이터는 확장 범위다.

## 프론트 연결 시 주의

- 원본 등록과 추출은 별도 요청이다. 작업 ID를 폴링한 뒤 상세를 조회한다.
- 금액/수량은 십진 문자열 또는 null. 화면용 변환과 전송값을 구분한다.
- `expected_version`으로 동시 수정 충돌을 처리한다. PATCH에서 미전달과 null은 다르다.
- 목록은 `quote_id/customer_name/issue_date/total_amount`를 사용한다. 기존 화면의 `id/client/date/amount`와 매핑한다.
- API_TOKEN이 켜졌다면 원본 다운로드도 인증 헤더가 필요하다.
- 초안 생성·AI 초안 제안은 현재 범위에서 제외한다. 저장된 견적의 Excel/PDF 사본 출력은 유지한다. API 예제와 오류 형식은 `README.md`를 확인한다.
