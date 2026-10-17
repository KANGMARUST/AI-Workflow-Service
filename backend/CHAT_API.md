# 견적서 기반 대화 API

저장된 견적서 1~5개를 선택해 한국어로 질문하고 이전 대화를 이어간다. 질문·답변·근거는 DB에 저장된다. 프론트엔드 구현은 별도 담당 범위이며 이 문서는 연동 계약이다.

AI는 기존 `UPSTAGE_API_KEY`로 Solar Chat Completions를 호출한다. Studio 추출/비교 Agent ID는 사용하지 않는다. 기본 모델은 `solar-pro4`이며 사용자는 허용 목록에서 대화별 모델을 선택·변경할 수 있다. 호출 규약은 [Upstage Chat API 공식 문서](https://console.upstage.ai/api/chat)를 따른다.

## 순서

1. 기존 등록·추출 API로 견적서를 저장한다. 추출 완료 또는 품목 입력이 된 활성 견적서를 사용한다.
2. `POST /api/chats`로 견적 ID들을 선택한다.
3. 반환된 `chat_id`와 `version`으로 질문한다.
4. 답변의 `chat.version`을 다음 질문에 사용한다. 오류가 나면 `GET /api/chats/{chat_id}`로 최신 버전을 읽는다.
5. 재접속 시 대화 목록과 메시지 이력을 조회한다.

접두사 `/api`는 `API_PREFIX` 설정을 따른다. 기존 `API_TOKEN` 인증이 켜져 있으면 모든 대화 API에도 Bearer 토큰을 보낸다. 현재 서비스의 공유 팀/워크스페이스 권한을 따르며 사용자별 대화 격리는 제공하지 않는다.

| 메서드 | 경로 | 결과 |
|---|---|---|
| POST | `/api/chats` | 대화 생성, HTTP 201 |
| GET | `/api/chats?limit=20&offset=0` | `{items,total,limit,offset}` |
| GET | `/api/chats/models` | 선택 가능한 모델 ID·표시명·기본 모델 |
| GET | `/api/chats/usage` | 저장된 전체 답변의 토큰 누적·모델별 집계 |
| GET | `/api/chats/{chat_id}` | 제목·견적 ID·모델·버전·생성 중 여부·누적 사용량 |
| PATCH | `/api/chats/{chat_id}` | 모델 변경, `model`·`expected_version` 필수 |
| GET | `/api/chats/{chat_id}/usage` | 해당 대화의 누적·모델별 토큰 집계 |
| POST | `/api/chats/{chat_id}/messages` | 질문과 AI 답변을 함께 저장, HTTP 201 |
| GET | `/api/chats/{chat_id}/messages?limit=20&offset=0` | 오래된 순서의 질문·답변 이력 |
| DELETE | `/api/chats/{chat_id}` | 대화·메시지 영구 삭제. 원본 견적은 유지 |

목록/이력의 기본 limit는 20, 최대 100이다. 메시지 이력은 `sequence` 오름차순이며 offset으로 페이지를 넘긴다.

## 요청·응답 예시

대화 시작:

```http
POST /api/chats
Content-Type: application/json

{"quote_ids":["견적-UUID"],"title":"센서 견적 검토","model":"solar-mini4"}
```

```json
{
  "chat_id":"대화-UUID",
  "title":"센서 견적 검토",
  "quote_ids":["견적-UUID"],
  "model":"solar-mini4",
  "version":1,
  "busy":false,
  "created_at":"2026-10-17T00:00:00+00:00",
  "updated_at":"2026-10-17T00:00:00+00:00"
}
```

질문 전송:

```http
POST /api/chats/대화-UUID/messages
Content-Type: application/json

{"content":"이 견적의 납기와 유효기간은?","expected_version":1}
```

```json
{
  "chat":{"chat_id":"대화-UUID","title":"센서 견적 검토","quote_ids":["견적-UUID"],"model":"solar-mini4","version":3,"busy":false,"created_at":"...","updated_at":"..."},
  "user_message":{"message_id":"질문-UUID","chat_id":"대화-UUID","sequence":1,"role":"user","content":"이 견적의 납기와 유효기간은?","sources":[],"metadata":{},"created_at":"..."},
  "assistant_message":{
    "message_id":"답변-UUID","chat_id":"대화-UUID","sequence":2,"role":"assistant",
    "content":"납기는 발주 후 4주, 유효기간은 견적일로부터 7일입니다. 발주일이 없어 확정 납기일은 알 수 없습니다.",
    "sources":[{"quote_id":"견적-UUID","version":4,"source_filename":"sample.xlsx","field_path":"delivery_period","value":"발주 후 4주","truncated":false}],
    "metadata":{"requested_model":"solar-mini4","model":"solar-mini4-260922","usage":{"prompt_tokens":100,"completion_tokens":50,"total_tokens":150},"insufficient_data":false,"history_messages_used":0,"history_truncated":false,"source_text_truncated":[],"quote_versions":[{"quote_id":"견적-UUID","version":4}]},
    "created_at":"..."
  }
}
```

`version` 증분을 클라이언트에서 계산하지 않는다. 생성 예약·완료·실패 처리에 따라 바뀌므로 서버 반환값을 사용한다. 동일 버전으로 중복 전송하면 409다. 성공 응답을 놓친 경우 이력부터 확인한다. 실패한 질문은 메시지로 남지 않으며 성공한 질문·답변 두 건만 원자적으로 저장한다.

위 대화 객체 예시에서는 사용량 필드를 생략했다. 실제 생성·상세·모델 변경 응답과 질문 응답의 `chat`에는 아래 형식의 `usage`도 포함된다. 대화 목록은 선택 모델을 반환하며 사용량은 상세 또는 사용량 API에서 조회한다.

## 사용자 모델 선택·변경

`GET /api/chats/models`의 기본 반환값:

```json
{"default_model":"solar-pro4","items":[{"id":"solar-pro4","name":"Solar Pro 4","default":true},{"id":"solar-mini4","name":"Solar Mini 4","default":false}]}
```

대화 생성 시 `model`을 생략하면 서버의 `CHAT_MODEL`을 선택해 저장한다. 기존 대화의 모델은 다음과 같이 변경한다:

```http
PATCH /api/chats/대화-UUID
Content-Type: application/json

{"model":"solar-pro4","expected_version":3}
```

반환된 대화 버전을 다음 질문의 `expected_version`으로 사용한다. 모델을 바꿔도 이전 질문·답변·근거·사용량은 유지하고 다음 질문부터 새 모델을 호출한다. 답변 생성 중 변경이나 오래된 버전은 409, 허용 목록에 없는 모델은 422다. 기존에 선택했던 모델이 서버 허용 목록에서 제거돼도 과거 이력은 유지하며 새 질문 전에 모델을 다시 선택해야 한다.

관리자는 `CHAT_ALLOWED_MODELS`의 쉼표 목록으로 선택지를 정한다. 기본 모델은 항상 선택지에 포함된다. 클라이언트가 보낸 임의의 모델이나 외부 API 주소를 호출하지 않는다. 목록은 서버 설정값이며 실제 계정의 모델별 권한·잔액은 실호출로 확인해야 한다.

## 표시할 토큰 사용량

답변별 사용량은 `assistant_message.metadata.usage`의 `prompt_tokens`(입력), `completion_tokens`(출력), `total_tokens`(전체)다. `requested_model`은 사용자가 선택한 모델이며 `metadata.model`은 공급자가 실제 반환한 모델 버전이다. 이전 대화 문맥도 입력 토큰에 포함된다.

`GET /api/chats/{chat_id}/usage`와 대화 상세의 `usage` 예시:

```json
{
  "basis":"saved_answers",
  "assistant_messages":2,
  "reported_messages":2,
  "missing_usage_messages":0,
  "prompt_tokens":2000,
  "completion_tokens":400,
  "total_tokens":2400,
  "complete":true,
  "by_model":[
    {"model":"solar-mini4","assistant_messages":1,"reported_messages":1,"missing_usage_messages":0,"prompt_tokens":1000,"completion_tokens":200,"total_tokens":1200,"complete":true},
    {"model":"solar-pro4","assistant_messages":1,"reported_messages":1,"missing_usage_messages":0,"prompt_tokens":1000,"completion_tokens":200,"total_tokens":1200,"complete":true}
  ]
}
```

- `basis=saved_answers`: DB에 저장된 답변의 공급자 보고값만 합산한다. 외부 계정의 청구액·잔여 한도·총 사용량 조회 API가 아니다. 실패·시간 초과·근거 검증 거절 등 저장하지 않은 답변의 사용량은 포함하지 않는다.
- `reported_messages`는 세 토큰 값이 모두 있는 답변 수, `missing_usage_messages`는 하나 이상 누락된 답변 수다. 누락 또는 비정상 값은 합산하지 않고 `complete=false`로 표시한다. 이때 합계는 확인된 값의 부분 합계이므로 화면에서도 누락 상태를 알려야 한다.
- `by_model`은 요청한 모델별로 집계한다. 이전 기록에 `requested_model`이 없으면 기록된 실제 응답 모델명으로 집계하며 모델명을 추정하지 않는다.
- `GET /api/chats/usage`는 공유 워크스페이스의 저장된 모든 답변을 같은 형식으로 집계한다. 견적이 휴지통에 있어도 전체 집계에는 남고, 대화·견적 영구 삭제로 답변 기록이 지워지면 해당 사용량도 빠진다.
- 금액 환산이나 잔액 추정은 하지 않는다. 프론트 담당자는 모델 선택 API와 이 사용량 필드를 연결해 화면에 표시한다.

## 견적 근거와 대화 문맥

- 매 질문마다 선택한 견적의 최신 수정값·품목·납기·유효기간·세금 조건·Decimal 정합성 검사를 읽는다. 2건 이상이고 전체 품목 수가 100개 이하이면 서버의 `verified_comparison`도 제공한다.
- 상대 기간, null, 명시된 0, VAT 별도 여부와 저장된 총액 필드를 혼동하지 않도록 지시한다. 자료 부족 시 `insufficient_data=true`와 확인 질문을 반환할 수 있다.
- 근거 필드 경로는 실제 선택한 견적의 값으로 제한한다. `sources.value`는 AI가 생성한 인용문 대신 서버가 읽은 값이다. 견적 ID·필드가 유효하지 않거나 자료 부족 표시 없이 근거가 없으면 502로 거절한다. 출처의 존재를 검증하는 기능이며 문장 전체의 정확성을 보증하는 것은 아니다.
- 출처의 `version`은 답변 당시 견적 버전이다. 과거 답변은 생성 당시 내용으로 보존한다. 답변 생성 중 견적서가 수정되면 결과를 저장하지 않고 409를 반환한다.
- 기존 사용자 질문과 AI 답변은 기본 최근 20개 메시지(10턴)를 재전송한다. 더 오래된 이력은 DB에서 조회할 수 있지만 모델 문맥에서는 제외되며 `history_truncated=true`다. 입력 한도에 맞추기 위해 오래된 턴이 추가로 제외될 수 있다.
- 현재 정형 필드에서 원문 보존용 `raw_fields`를 제외한 값을 제공한다. 원문 텍스트는 견적별 앞 12,000자를 1,000자씩 `source_chunks`로 나눠 제공한다. 이후 내용이 있으면 `source_text_truncated`에 해당 견적 ID를 반환한다. 절단된 부분에 대한 답변은 확인이 필요하다.
- 질문은 4,000자까지이며 메시지로 전달하는 문맥은 기본 60,000자다(출력 JSON 스키마 제외). 정형 자료와 질문이 한도를 넘으면 413이다. 토큰 한도와 별도의 문자 수 제한이다.
- 문서 안의 지시는 데이터로 취급하며 실행 도구를 제공하지 않는다. 이 API는 답변만 생성한다. 견적 초안 생성·수정·확정·삭제·메일 전송 기능은 제공하지 않는다.

## 저장·삭제·동시 요청

- `quote_chats`에 제목·선택한 견적 ID·선택 모델·버전·진행 상태를, `quote_chat_messages`에 질문·답변·근거·요청/실제 모델명·토큰 사용량을 저장한다. API 키와 모델의 reasoning 원문은 저장하지 않는다.
- 동일 대화의 동시 질문은 409다. 서로 다른 대화는 별도로 처리한다. 응답은 한 번에 반환하는 JSON이며 토큰 스트리밍/SSE는 현재 지원하지 않는다.
- 서버 재시작 시 진행 표시를 해제한다. 미완료 질문은 이력에 추가하지 않으며 사용자가 최신 버전으로 재시도한다. 현재 서버의 단일 worker 실행 조건을 따른다.
- 선택한 견적 중 하나라도 휴지통에 있으면 해당 대화는 목록에서 숨기고 이력 조회·질문을 차단한다. 원본을 복원하면 다시 조회할 수 있다.
- 견적을 영구 삭제하면 그 견적을 선택한 대화와 메시지도 함께 영구 삭제한다. 여러 견적을 선택한 대화 전체가 삭제되므로 대화 안의 다른 견적에 관한 답변도 함께 사라진다.
- 대화 삭제는 원본 견적을 삭제하지 않는다. 답변 생성 중인 대화의 직접 삭제는 409다.

## 설정·DB 적용

```dotenv
UPSTAGE_API_KEY=서버에서만 관리
CHAT_BASE_URL=https://api.upstage.ai/v1
CHAT_MODEL=solar-pro4
CHAT_ALLOWED_MODELS=solar-pro4,solar-mini4
CHAT_TIMEOUT_SECONDS=60
CHAT_MAX_TOKENS=2048
CHAT_MAX_CONTEXT_CHARACTERS=60000
CHAT_HISTORY_MESSAGES=20
```

`CHAT_HISTORY_MESSAGES`는 짝수로 지정한다. `/api/capabilities`의 `chat`에 키 설정 여부·기본 모델·허용 모델 ID 목록(`models`)·최대 견적 수·스트리밍 지원 여부를 제공한다. `configured=true`는 키가 있다는 의미이며 실제 모델 접근 권한·잔액을 보장하지 않는다.

SQLite는 앱 시작 시 대화 테이블을 추가하고, 이전 대화 테이블에 `model` 열이 없으면 nullable 열을 추가한다. 기존 견적·대화 내용은 변경하지 않는다. 모델이 없는 이전 대화는 서버 기본 모델을 사용하고 첫 질문 또는 모델 변경 시 선택값을 저장한다.

기존 PostgreSQL에는 대화 기능 최초 설치 시 `supabase/migrations/20261017_quote_chat.sql`, 사용자 모델 선택 추가 시 `supabase/migrations/20261017_chat_model.sql`을 순서대로 적용한다. 새 빈 DB에는 `supabase/schema.sql`을 사용한다. 대화 테이블에는 RLS를 활성화하고 익명 정책을 만들지 않는다. 외부 DB에는 이번 작업에서 적용하지 않았다.

| 상태 | 의미 |
|---|---|
| 401 | 서비스 Bearer 토큰 누락/불일치 |
| 404 | 대화·견적 없음 또는 선택한 견적이 휴지통에 있음 |
| 409 | 대화 버전 충돌, 답변 생성 중, 견적 추출 미완료/진행 중, 생성 중 견적 변경 |
| 413 | 견적·질문 문맥이 문자 수 한도 초과 |
| 422 | 빈 질문, 중복 견적 ID, 선택 수·질문 길이 등 입력 오류 |
| 502 | 외부 연결/응답 오류 또는 유효하지 않은 근거 |
| 503 | API 키/모델 설정·접근 권한·호출 한도 또는 DB 접근 오류 |
| 504 | AI 답변 시간 초과 |

가상 XLSX를 사용하는 실제 대화 테스트(외부 API 사용량 발생):

```powershell
backend/.venv/Scripts/python.exe -u backend/tools/live_chat_check.py --live
# 모델 변경 및 모델별 토큰 집계까지 검증:
backend/.venv/Scripts/python.exe -u backend/tools/live_chat_check.py --live --model solar-mini4 --switch-model solar-pro4
```

원본 사용자 파일 대신 가상 견적만 사용하며 별도 `.runtime/live-chat-check/` DB·결과에 두 번의 질문과 답변을 저장한다.
