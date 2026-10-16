# QuoteFlow Studio 에이전트

2026-10-16, 사용자 Chrome의 로그인된 Upstage Studio에서 구성·실행했다. `project/`의 코드나 설정은 사용하지 않았다. JSON 파일은 Studio의 실제 설정 내보내기 결과다. 이후 FastAPI 호출 연동을 구현하고 사용자 키로 가상 PDF 실호출을 검증했다. 공개 게시와 API 키 발급은 수행하지 않았다.

## 기준

- 기획서: https://app.notion.com/p/3f827af47d0e802e9c04d6a9dc6c68e0
- 사용 가이드: https://ku-sejong-hackathon-playbook.vercel.app/#sec5
- 현재 범위는 추출·검토·검색·조건별 단가 비교다. 초안 생성 및 AI 초안 제안은 사용자 요청으로 제거했다.
- 가이드의 문서 → Parse → Extract → JSON 패턴을 적용했다. 출력 스키마를 동일하게 유지하므로 Classify 분기 대신 결과 상태 필드를 사용한다. AI 검토는 사용자 확정을 대신하지 않는다.

## 연결 정보

| 역할 | Agent ID | Config ID |
|---|---|---|
| 견적 추출·검토 | `agt_PDRAagZCX2rzbqfEm7J5QA` | `3` |
| 조건별 단가 비교 | `agt_Tm6UnDBS47q2W3EJ5NEQKQ` | `1` |

```dotenv
QUOTE_EXTRACT_AGENT_ID=agt_PDRAagZCX2rzbqfEm7J5QA
QUOTE_EXTRACT_CONFIG_ID=3
QUOTE_COMPARE_AGENT_ID=agt_Tm6UnDBS47q2W3EJ5NEQKQ
QUOTE_COMPARE_CONFIG_ID=1
```

위 변수명은 현재 `app/config.py`가 읽는다. `UPSTAGE_API_KEY`는 로컬 `.env`에서만 관리한다. 다른 계정에서는 JSON을 가져온 뒤 그 계정의 Agent/Config ID를 다시 확인해야 한다. 전체 API 계약은 `../README.md`를 참고한다.

## 입력·출력

- **추출:** 견적 PDF → 헤더, `items` 배열, `review_warnings`, 원문 보존용 `raw_fields_json`. XLS/XLSX는 백엔드에서 표시 시트의 셀을 읽고 PDF로 조립해 전달한다. 원본 Excel을 Studio에 직접 보내지 않는다. 지정된 XLS 1개와 PDF 2개 실호출은 `../INPUT_DOCUMENTS.md`에 정리했다.
- **비교:** 검색한 과거 견적들의 ID·품목·규격·단위·통화·수량·날짜·거래조건을 백엔드가 한 PDF로 조립해 전달한다. `comparison_status`, 비교 행, 비교쌍, 제외 항목, 확인 질문을 반환한다. 동일 품목명만으로 같은 규격이라고 가정하지 않는다.

숫자는 십진 **문자열**, 미기재는 빈 문자열이다. Studio Number 필드에서 누락 수량이 0으로 반환되는 사례를 확인해 타입을 바꾸고 재검증했다. 백엔드에서 빈값은 `None`, 명시된 값만 `Decimal`로 변환해야 한다. 0은 유효한 값일 수 있으므로 일괄 결측 처리하지 않는다.

`*_json` 필드는 JSON을 담은 문자열이다. 바깥 응답 파싱 후 `json.loads`로 한 번 더 파싱하고 스키마를 검증한다. 금액·차액·비율은 백엔드에서 재검산한다. 금액 정합성 검사는 AI 문장만으로 확정하지 않는다.

## Studio에서 확인한 결과

| 샘플 | 확인 결과 |
|---|---|
| 정상 견적 | 품목 3개, 공급가액 500000, 세액 50000, 총액 550000 추출 |
| 오류 견적 / 추출 v3 | 품목 3개 보존, 수량 미기재를 빈값으로 유지. 원문 190000 보존. 수량×단가 200000과의 차이 및 품목 합계 490000/공급가액 500000 불일치 경고 |
| 비교 / v1 | A/B를 조건부 비교, 단가 차이 -2000 및 -8% 표시. 수량·결제·운송 조건 차이 명시. 규격·단위·통화가 다른 C 제외 |

`results/`의 CSV는 Studio UI에서 내려받은 실제 샘플 결과다. 이후 같은 가상 PDF로 외부 API 3개 호출과 로컬 HTTP 서버 통합 흐름을 검증했다. 실호출 결과는 Git 제외 경로 `../.runtime/live-agent-check/`에 있다. 실제 다양한 기업 양식·스캔/OCR·프론트 UI 통합은 검증하지 않았다. 일부 테스트 문서에는 검증 메모가 포함되므로 실제 정확도 평가 자료로는 사용할 수 없다.

## 구현된 백엔드 흐름

1. 파일 원본 보관과 DB 영속 저장, 목록·상세·원본 접근을 구현했다.
2. Files API 업로드 → Responses 작업 생성 → 상태 폴링 → JSON 검증을 연결했다. 기준 주소는 `https://api.upstage.ai/v2`다. 타임아웃·실패·명시적 재시도와 임시 파일 정리를 지원한다.
3. 추출 원문/결과/검토 경고를 저장하고 사용자 수정·확정을 연결했다.
4. 선택한 DB 견적을 비교 입력 PDF로 조립한다. AI 비교와 별도로 Decimal 검산 결과를 제공한다.
5. 저장된 견적의 지정 양식 Excel/PDF 사본 출력은 유지한다.

## 설정 재사용 및 샘플 재생성

Studio의 워크플로우 목록 → 설정 일괄 가져오기로 JSON을 불러온다. 기존 워크플로우의 설정 가져오기는 버전 변경이므로 대상 이름을 확인한다. 실행 후 설정 번호와 출력 JSON을 확인하고 새 JSON을 내보낸다.

샘플은 개인정보가 없는 가상 자료다. 선택적으로 Windows에서 재생성할 수 있다.

```powershell
uv pip install --python backend/.venv/Scripts/python.exe -r backend/tools/requirements.txt
backend/.venv/Scripts/python.exe backend/tools/build_agent_samples.py
```

샘플 생성기는 Windows의 `C:/Windows/Fonts/malgun.ttf`를 사용한다. 다른 OS에서는 폰트 경로를 바꿔야 한다. 서버의 ReportLab 출력은 `app/fonts/`에 동봉한 나눔고딕을 사용한다.
