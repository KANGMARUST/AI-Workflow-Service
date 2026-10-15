# API 계약 초안

- `POST /api/add`: multipart/form-data `file`
- `GET /api/extract?quote_id={id}`: 추출 결과 조회
- `POST /api/search`: JSON 조건 `keyword`, `customer_name`, `item_name`, `date_from`, `date_to`, `amount_min`, `amount_max`, `status`, `limit`, `offset`
- `GET /api/search?keyword=...&limit=20&offset=0`: 간단 검색
- `GET /api/cards?status=...&limit=20&offset=0`: 목록 조회
- `PATCH /api/edit/{quote_id}`: 변경할 필드만 전달
- `GET /api/status/{quote_id}`: 상태 조회
- `POST /api/status/{quote_id}`: `{"status":"confirmed","note":"원본 대조 완료"}`

모든 응답은 현재 스텁입니다. 실제 추출 실행은 GET에 넣지 말고 POST 작업 API로 분리하는 것을 권장합니다.
