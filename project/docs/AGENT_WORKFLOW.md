# 견적 아카이브 에이전트·API 개발 기록

## 개인 API 키 포함 여부 점검 (2026-10-14)

웹 API 설정의 키 입력값 없음·API 미적용·로컬 분석 상태를 확인했다. 개인 키를 메모리에서 대조한 프로젝트 관련 85개 파일(소스·설정·빌드·DB·백업·로그)에 동일 키와 실제 키 형태의 검출이 없었다. 배포 서버는 요청 헤더의 사용자 키만 받으며 개발 테스트 전용 개인 키 파일을 사용하지 않는다. 향후 사용자가 자신의 키를 웹에 입력하는 기존 구조를 유지한다. 키 값은 출력·기록하지 않았고 실 API 호출은 0회다. 범위·한계와 결과: DEVELOPMENT.md 및 tests/api-key-presence-results.json.

## 프로젝트 외 Studio 에이전트 정리 (2026-10-14, 삭제 완료)

사용자가 이번 프로젝트 외 에이전트 삭제를 요청했다. 기존 별도 에이전트 보존 지침에 대한 이번 명시적 변경 요청으로 처리한다. 실제 Studio 목록은 8개이며 견적아카이브_추출·검토·비교 3개의 이름과 기존 Agent ID 일치를 확인했다. 삭제 후보 5개만 선택하여 일괄 삭제 확인창까지 준비했다.

| 삭제 후보 | Agent ID |
|---|---|
| 장사비서_Diagnosis_Prototype | agt_kcxKzHX72nEdkBX85Lg6TS |
| 장사비서_Operations_Prototype | agt_kahDBJdyLReYPTrgt76yEZ |
| 장사비서_Sales_Prototype | agt_fnoXKSVEA6KQRwki2diJz6 |
| Resume Agent | agt_Yeph3d4ugRu2ojkNt2FkWK |
| 강희찬_미션1_JD Agent | agt_WcvLf52o5BAhzbLg93ZTMW |

Studio 확인창은 삭제한 워크플로우는 복구할 수 없고, 완료된 실행·결과는 유지되며 진행 중 실행은 취소된다고 안내했다. 사용자가 영구 삭제를 최종 확인한 뒤 위 5개를 일괄 삭제했다. 관련 파일 7개 추가 삭제 옵션은 모두 선택하지 않고 실행했다. 삭제 처리 완료 후 실제 목록에 견적아카이브_추출·검토·비교 3개만 남아 있으며 이름과 Agent ID가 프로젝트 기록과 일치함을 확인했다. 화면 증거: tests/qa/studio-agent-delete-confirmation.jpg, tests/qa/studio-agents-after-delete.jpg. 기존 로컬 DB·원본·프로젝트 에이전트 설정은 변경하지 않았다. 파일·기존 실행 결과의 개별 목록은 별도로 재검증하지 않았다.

## 기준과 현재 상태

참고 가이드북: https://ku-sejong-hackathon-playbook.vercel.app/
생성 절차는 4장(#sec5), 팀 문서 적용은 4-8(#sec5-8), 제출 설정 내보내기는 7-1(#sec8-1)을 따른다.
2026-10-14 사용자 요청: 에이전트를 핵심 기능에 적극 활용하고 개발자가 직접 생성한다. 실연결 테스트에 사용자 API 사용을 허용했다. API 키를 배포 앱의 공용 키로 저장한다는 뜻은 아니다.

현재 구현 완료: PDF 업로드 시 사용자가 입력한 Upstage Studio 에이전트로 견적 정보를 구조화하는 선택 실행 경로. 사용자별 API 설정 및 가이드북 링크. 서버 공용 키 사용 경로 제거. 모의 API 5건과 통합 테스트 20건 통과 기록.
현재 추가 완료: 견적 전용 Studio 에이전트 3개 생성·이름 지정·실제 설정 내보내기, 검토·비교 작업실, 사용자 API를 이용한 가상 견적 실연결 검증. 이전 모의 테스트와 이번 실제 API 검증을 구분한다.

## 구현된 에이전트 역할

| 역할 | 입력 | Studio 노드 | 출력과 웹 활용 |
|---|---|---|---|
| 견적 추출 | 기존 견적 원본 PDF·Excel·Word·이미지 | Parse → Extract | 회사·견적 식별·날짜·거래 조건·반복 품목·단가·원문 금액 JSON. 신규 PDF 등록에는 추출값을 저장하고, 작업실 재추출은 비교용 보고서로 따로 저장 |
| 견적 검토 | 보관된 견적 데이터와 출처를 조립한 분석 입력 PDF | Parse → Classify → Extract | 누락·금액 불일치·옵션·조건 확인 사항과 근거. 원본 값과 구별하여 표시 |
| 견적 비교 | 선택한 여러 견적 JSON을 조립한 분석 입력 PDF | Parse → Classify → Extract | 품목·사양·단가·조건의 차이, 비교 불가 이유 및 문서별 근거 |

미기재 값은 추정하지 않는다. 옵션을 임의로 선택하거나 VAT·합계를 새로 채우지 않는다. 분석용 중간 PDF는 기존 데이터 전달용이며 새 견적서 작성 기능이 아니다. AI 제안은 원본 값을 자동 변경하거나 사람의 검토 완료 상태를 대신하지 않는다.

## 현재 API 호출 흐름

1. 웹의 API 설정에서 사용자가 Upstage API Key, Agent ID, Config ID와 외부 전송 동의를 입력한다. 키는 현재 탭의 React 메모리에만 유지한다.
2. 업로드 요청에 X-User-API-Key, X-User-Agent-ID, X-User-Config-ID, X-User-AI-Consent 헤더를 붙여 프로젝트 서버로 전달한다. 일반 조회·검색에는 키를 보내지 않는다.
3. backend/user_agent.py의 settings_from_request가 동의·입력 형식·공개 환경 HTTPS를 검사한다. AgentSettings는 요청 범위이며 repr에서도 키를 숨긴다.
4. run_agent는 고정 https://api.upstage.ai/v2에서 POST /files(purpose=user_data)로 PDF를 업로드한다.
5. POST /responses에 model=Agent ID, config_id=설정 버전, include=[last], input_file.file_id를 보내 실행한다.
6. queued/in_progress이면 GET /responses/{response_id}로 상태를 조회한다. completed 결과의 output_text 또는 output의 텍스트를 JSON 객체로 해석한다.
7. 키가 포함된 값과 인증 필드는 제거한다. merge_agent_result는 허용된 견적·품목 필드만 반영한다. 에이전트 식별자와 응답 식별자는 agent_analysis에 남긴다.
8. 요청에서 업로드한 원격 임시 파일은 종료 시 삭제를 시도한다. 오류 응답의 원문·키를 사용자 화면에 전달하지 않는다.

서버 .env·DB·소스·로그·이 문서에 사용자 키를 기록하지 않는다. 배포 앱은 각 사용자가 넣은 키로만 실행한다. 개발 테스트용 API는 허가된 테스트 과정에서만 사용하고 배포 설정에 복사하지 않는다.

## 검증 기록 방식

Studio 생성 확인 시 역할별 실제 Agent ID·Config ID·노드·내보낸 설정 파일 경로를 기록한다. 키 값은 제외한다. 실제 API 테스트는 가상 테스트 견적을 사용하며 날짜·단계·응답 ID·성공/실패·소요 시간·기대값 비교를 기록한다. 모의 검증과 실연결 검증을 구분한다. 진행 중·실패·미검증도 사실대로 남긴다.

## 진행 기록

- 2026-10-14: 가이드북의 Parse/Extract 및 Parse/Classify/Extract 생성 절차와 JSON → PDF → 평가 에이전트 흐름을 다시 확인했다. 웹은 React/FastAPI를 유지하며 가이드북의 역할 분리를 적용한다.
- 2026-10-14: 에이전트 역할, 현재 구현된 API 흐름, 사용자 API 테스트 허가 범위, 미완료 항목을 기록했다. 견적 전용 에이전트 생성과 웹 확대 구현은 진행 중이다.

## Studio 생성 완료

가이드북 스타터 설정 형식을 사용해 견적 전용 스키마를 작성하고 Studio의 '워크플로우 설정 일괄 가져오기'로 3개를 생성했다. 가져오기 직후 이름이 Workflow로 표시되어 각각 이름을 편집했다. 기존 장사비서·HR 워크플로우는 변경하지 않았다. 설정 버전은 모두 1이다. 각 실제 설정을 Studio에서 내보내 agent_configs에 보관했다.

| 실제 이름 | Agent ID | Config ID | 설정 파일 |
|---|---|---|---|
| 견적아카이브_추출 | agt_WUmdoTPSummj3uQ7Qdi6dM | 1 | agent_configs/견적아카이브_추출.json |
| 견적아카이브_검토 | agt_3meY3NJetTYi7X9n8RTPpB | 1 | agent_configs/견적아카이브_검토.json |
| 견적아카이브_비교 | agt_R5gPHUeVuUoDCheCftTnDL | 1 | agent_configs/견적아카이브_비교.json |

추출은 단일 Extract 19항목이다. 반복 품목은 items_json 문자열을 JSON 배열로 해석해 기존 items 필드에 연결한다. 검토 분류는 확인 필요/주의/문제 없음이며 분기별 동일 summary/risk_level/findings/recommendations 스키마다. 비교 분류는 비교 가능/조건부 비교/비교 불가이며 분기별 동일 summary/comparison_level/differences/limitations 스키마다.

## 웹 및 DB 연결 완료

웹의 API 설정에는 **견적아카이브_추출**의 Agent ID를 입력한다. 이 값은 새 PDF 등록과 작업실에서 원본 재추출을 선택할 때 사용한다. 검토·비교는 작업실에서 역할을 선택해 해당 Agent ID·Config ID를 입력한다. API Key는 계정 인증용이고 Agent ID는 실행 대상, Config ID는 저장된 설정 버전이라는 설명과 역할별 이름·용도·입력 위치·실제 ID 표를 API 설정 화면에 제공한다. 작업실도 선택한 역할의 Studio 이름과 설명을 표시하며 전체 안내로 이동할 수 있다. 다른 계정은 접근 가능한 자신의 역할별 ID·버전을 사용한다.

기본 화면을 에이전트 작업실로 변경했다. 초기 구현은 원본 PDF 재추출 1개, 형식에 관계없는 보관 문서 검토 1개, 비교 문서 2~5개 선택이었다. 현재 다중 선택과 비 PDF 재추출 범위는 아래 확장 기록을 따른다. 각 역할의 Agent ID·Config ID는 작업실에서 수정할 수 있다. 본인 API 설정·동의가 없으면 실행하지 않으며 서버에서도 차단한다. 위 에이전트 ID는 생성 계정 소유이므로 다른 사용자는 접근 가능한 자신의 Agent ID로 교체해야 한다.

POST /api/agent-runs가 요청별 인증 설정을 확인하고 backend/agent_workflow.py의 execute를 실행한다. 검토·비교는 원본 식별자·견적 버전·품목·단가·금액·사양·조건을 조립한 중간 PDF를 만들고 공통 run_agent로 전송한다. 개발자의 코드가 수행하는 PDF 조립과 Studio AI가 수행하는 해석·분류·비교를 구분한다. 키는 분석 입력에 포함되지 않는다. 사용된 로컬 임시 PDF는 완료/실패 때 삭제한다.

agent_runs 별도 테이블에 실행 ID, 역할, 대상 문서 ID와 버전, 상태, 시작·완료 시간, Agent ID/Config ID, 결과 JSON 또는 안전한 오류, Upstage response_id를 보관한다. GET /api/agent-runs로 작업실에서 이력을 조회한다. 휴지통 문서와 연결된 보고서는 조회에서 제외하며 복원하면 다시 볼 수 있다. 원본 견적과 사용자 정정값·원본 파일·금액·검토 완료 상태는 작업실 실행으로 변경하지 않는다. 결과 JSON은 AI 응답이며 사용자가 원문 근거를 확인한다.

## 실제 사용자 API 검증 (2026-10-14)

사용자가 API 테스트를 허용한 뒤 테스트 전용 스크립트 tests/live_quote_agents.py에서 부모 폴더 SaveAPI.md의 Upstage 키를 메모리로 읽어 사용했다. 키 값을 출력하지 않았고 웹 소스·설정·DB·개발 문서로 복사하지 않았다. 이 스크립트는 서버에서 import하지 않는 개발 테스트용이며 배포 웹은 계속 사용자 요청 헤더만 사용한다. 실제 회사 원본 대신 Test_input_data의 가상 T01/T02 견적만 전송했다.

| 단계 | 실제 API 응답 ID | 소요 시간 | 검증 결과 |
|---|---|---|---|
| T01 추출 | job_LvhnAh2uVdmXyhcyEKhWHW | 20.97초 | 고객, 3품목, 단가, 총액 495000 일치 |
| T02 추출 | job_hhCnFPKKbwXVwMa9Cmmatp | 18.03초 | 고객, 3품목, 단가, 총액 520300 일치 |
| T01 추출 JSON → 검토 PDF → 검토 | job_V5kZLoPQvxbXjQAoJcSwji | 31.36초 | 문제 없음 분류, 문서 ID와 품목별 금액 근거, 납품지 확인 사항 출력 |
| 두 추출 JSON → 비교 PDF → 비교 | job_fN6xhku4Nr5mbQAxZhjncG | 37.26초 | 비교 가능 분류, 브라켓 12000→13500·센서 45000→47000 차이와 문서 근거 출력 |

실제 에이전트 호출 4회, 기대값 자동 대조 15개 통과. 기록은 tests/live-agent-results.json에 가상 데이터와 응답 식별자를 저장했다. 테스트 결과를 사용자 회사 문서의 agent_runs에 가짜 실행 이력으로 등록하지 않았다. 실제 API의 입출력 흐름은 검증했으며 기존 회사 문서를 웹 버튼으로 외부 전송하는 실연결은 수행하지 않았다.

한계: T02 notes에는 원본 업무 비고 대신 테스트 표기가 일부 추출되었다. 비교 에이전트도 이 비고의 비교 불가를 표시했다. API 성공을 모든 필드의 정확성으로 해석하지 않는다. 원본 PDF 재추출만 지원하며 Excel/Word/이미지는 기존 로컬 등록 후 검토·비교를 실행한다. PDF 원본을 외부 분석할 때 가려진 내부 텍스트까지 읽을 수 있는 외부 서비스 특성은 남아 있으므로 검토용 입력은 구조화된 저장 데이터로 조립한다.

최종 검증: 기존 통합 테스트 20/20, 사용자 API 모의 테스트 5/5, 작업실·보고서·API 요청 검증 5/5 통과. production build 통과. 브라우저에서 작업실 기본 표시, 실제 등록 문서 3건, 역할별 ID 변경, 2문서 비교 선택, API 미적용 시 실행 차단을 확인했다. 문서 3건과 원본 금액·검토 상태를 변경하지 않았다. 웹 화면 증거는 tests/qa/agent-workspace.png에 보관한다.

## 작업실 다중 파일 및 비 PDF 재추출 확장 (2026-10-14)

작업실에서 PDF·Excel(.xls/.xlsx)·Word(.docx)·이미지(.png/.jpg/.jpeg)를 여러 개 등록한다. 이 단계는 기존 `/api/upload`의 로컬 분석만 사용해 보관함에 원본을 저장하며, 등록만으로 Studio에 보내지 않는다. 재추출과 누락·금액·조건 검토는 최대 5문서를 선택해 각 문서에 별도의 `POST /api/agent-runs` 요청을 순서대로 보내고 각 결과를 기존 `agent_runs`에 문서별로 보관한다. 한 문서가 실패해도 다음 문서를 처리하며 화면에 문서 이름별 오류를 표시한다. 비교는 기존처럼 2~5문서를 한 번의 분석 입력 PDF로 묶는다.

원본 재추출은 보관된 원본 파일의 실제 확장자와 MIME 형식으로 Upstage Files API에 전송한다. Parse 입력 요구사항은 이 7개 확장자를 지원하지만, 이 프로젝트 Studio 추출 에이전트의 비 PDF 실호출 정확도는 아직 검증하지 않았다. 검토는 원본 형식과 관계없이 저장된 구조화 값을 분석용 PDF로 조립해 전송한다. 원본·정정·검토 완료 상태는 이 작업으로 바뀌지 않는다. 출처: https://console.upstage.ai/docs/capabilities/parse/input-requirements 및 https://console.upstage.ai/docs/agents.
