# 기획 및 데이터 문서

## 서비스 목적
견적서에서 거래처, 담당자, 연락처, 제목, 품목, 수량, 단가, 조건을 추출해 검색 가능한 데이터베이스로 관리합니다. 과거 견적 검색과 동일 품목 단가 비교, 수정본 확인에 드는 시간을 줄입니다.

## 입력 형식
1차 지원: Excel `.xlsx`, 텍스트 선택 가능한 PDF `.pdf`. 확장: `.xls`, `.docx`, 스캔 PDF, JPG/PNG(OCR).

## 처리 흐름
파일 업로드/원본 보관 → 표·텍스트 추출 → Upstage 항목 분류 → 날짜·숫자·단위·통화 표준화 → 금액 정합성/품목 누락 검사 → 담당자 검토 후 확정 저장.
원문 표현과 표준화 값을 함께 보관하고, 불명확한 값은 임의로 채우지 않습니다.

## 주요 데이터
- 견적서: 견적번호, 발행 회사, 고객사, 작성일, 담당자, 유효기간, 납기일, 원본 파일
- 품목: 품목명, 규격, 단위, 수량, 단가, 품목별 금액 (견적서 1건에 여러 품목)
- 조건: 공급가액, 부가세, 총액, 통화, 할인/거래 조건
- 관리: 검토 상태, 등록일, 원문 및 표준화 값

## API 초안
| Method | Path | 목적 |
|---|---|---|
| POST | `/api/add` | 파일 등록 |
| GET | `/api/extract?quote_id=...` | 추출 결과 조회 |
| POST / GET | `/api/search` | 복합/키워드 검색 |
| GET | `/api/cards` | 목록 데이터 |
| PATCH | `/api/edit/{quote_id}` | 견적서 부분 수정 |
| GET / POST | `/api/status/{quote_id}` | 상태 조회/변경 |

상태 초안: `review_required`(확인 필요), `extracting`(추출 중), `confirmed`(검토 완료), `rejected`(반려), `archived`(보관).

## 추가 권장 API
- `POST /api/extract` 또는 `POST /api/extraction-jobs`: 실제 추출 작업 시작
- `GET /api/quotes/{quote_id}`: 상세 및 품목 조회
- `GET /api/quotes/{quote_id}/source`: 원본 파일 접근 URL 발급
- 인증/권한, 삭제/보관 정책, 중복 파일 검사도 별도 설계 필요
