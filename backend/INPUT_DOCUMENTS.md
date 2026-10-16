# 지정 견적서 3개 지원·검증

`docs/input-data/`의 아래 견적서만 대상으로 읽기와 실제 Upstage 추출을 확인했다. CSV, README, `~$` 임시 파일은 대상이 아니다. 입력 원본을 변경하지 않고 백엔드에서 필요한 전처리·행 대조를 수행한다. 초안 생성 기능은 추가하지 않았다.

## 처리 결과

| 파일 | 읽은 내용 | 금액 및 조건 처리 |
|---|---|---|
| `18KJ_ACT(InTouch 견적 건)_1122.xls` | 표시 시트의 품목 3개, 작성일 2018-11-22 | 선택 옵션을 유지하고 공급가액·총액을 임의 합산하지 않음 |
| `26KJ_POSCODX(3후판전단 AI)_261013_261013.pdf` | 품목 3개, 수량 4·2·4 및 규격 | 공급가액 16,000,000원. VAT 별도이며 세액·세금 포함 총액은 미기재로 유지 |
| `26KJ_포스코디엑스_포스코항만BTC_1012_261013_221912.pdf` | 상위 품목 5개와 구성품 15개, 총 20개 기록 | 상위 품목 기준 공급가액 266,740,000원. 반복 요약 및 구성품 이중 합산 방지 |

두 PDF 모두 `total_amount`를 공급가액으로 대신 채우지 않는다. 세금 포함 지급 총액은 원문에 명시되지 않았으므로 `null`이다. XLS의 여러 옵션도 전부 구매하는 것으로 가정하지 않는다.

## 구현

- `.xls` 등록·파일 내용 검증 및 `xlrd` 읽기를 추가했다. 원본 XLS 다운로드도 가능하다.
- 숨김 관리 시트를 제외하고 날짜, 0, 저장된 수식 결과, 빈 셀을 구분한다. 수식·매크로·외부 연결은 실행하지 않는다.
- Excel은 표시 셀을 행·열 위치가 있는 PDF로 조립한 뒤 기존 추출 에이전트로 전달한다. Studio에 원본 XLS를 직접 넣는 방식이 아니다.
- 한글·한자·영문 표 헤더 및 병합 셀 사이 빈 칸을 고려한다. 가격 없는 옵션 안내·주소 같은 문구를 품목으로 추가하지 않는다.
- PDF의 명시적 `품명 → 수량 → 단위 → 단가 → 금액` 열 순서를 읽어 AI가 놓치거나 잘못 연결한 수치와 행을 대조한다. 번호 있는 행을 명확히 읽지 못하면 일부만 덮어쓰지 않는다.
- 페이지 간 번호·품명·수량·단위·가격·금액이 같은 요약은 한 번만 남기고 반복 페이지 정보를 보존한다.
- 구성품과 상위 품목을 연결하고 가격 없는 사양 문구는 규격에 붙인다. 구성품 금액을 상위 금액에 다시 더하지 않는다.
- 선택 옵션은 `option_selection_required`, 상위/구성품 관계는 `hierarchical_items` 경고로 반환한다.
- 대조 전 AI 응답은 DB의 `extraction_raw.agent_fields`, 대조 후 결과는 `extraction_raw.fields`에 남는다. `GET /api/extract`의 `source_fields`는 대조 후 결과다.

## API 사용

1. `POST /api/add`에 원본 파일을 multipart `file`로 등록한다.
2. `POST /api/extraction-jobs`에 `{"quote_id":"...","provider":"upstage"}`를 보낸다.
3. `GET /api/jobs/{job_id}`에서 완료·실패를 확인한다.
4. 상세·추출 결과를 조회하고 원본과 검토 경고를 확인한다.

파일명별 전용 API는 없다. 동일한 등록·추출 API를 사용하며 `/api/capabilities`에 `.xls`, `.xlsx`, `.pdf`를 제공한다. 이미 데이터가 있는 견적을 다시 추출하려면 기존 값을 바꿀 수 있으므로 `force: true`를 명시한다.

## 재현

저장소 루트의 PowerShell:

```powershell
uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -u backend/tools/check_input_documents.py
# 지정 문서를 외부 Upstage로 전송하고 API 사용량이 발생하는 실연결 확인
backend/.venv/Scripts/python.exe -u backend/tools/check_input_documents.py --live
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=backend/.runtime/input-tests
```

`--input-dir`로 검사 폴더를 지정할 수 있다. `.xls/.xlsx/.pdf`만 검사하고 `~$` 파일은 건너뛴다. 실행 도구의 TestClient는 테스트 중 작업 완료까지 기다리지만 실제 프론트에서는 작업 ID 폴링이 필요하다.

검증 결과와 별도 테스트 DB·원본 사본은 Git 제외된 `backend/.runtime/input-document-check/`에 저장한다. 결과에는 문서 데이터가 포함되므로 그대로 공개 자료에 첨부하지 않는다. 기본 서비스 DB에는 이 도구가 견적을 등록하지 않는다.

## 검증과 한계

2026-10-16에 세 파일의 등록 → 실제 Studio 호출 → 정규화·원문 행 대조 → 저장을 완료했다. 이후 표시 시트의 행 대조를 보강하고 기록된 실호출 결과로 세 파일의 최종 행·금액 조건을 재검증했다. 자동 테스트 44개와 지정 Ruff 규칙 검사도 통과했다.

확인 범위는 지정한 세 문서다. 임의의 모든 기업 양식과 OCR 정확도를 보증하지 않는다. PDF는 화면에 보이는 값과 숨은 텍스트 레이어가 다를 수 있다. 원문 행 대조는 텍스트 레이어를 사용하며 담당자·연락처 같은 헤더를 이 값으로 덮어쓰지 않는다. 가린 부분이 있는 PDF의 텍스트 원문을 열거나 공유할 때도 이 차이를 고려해야 한다.

미기재 날짜·세액·총액은 추정하지 않으며 상대적인 유효기간·납기는 확정 날짜로 만들어 채우지 않는다. 실제 확정 전 담당자의 원본 검토는 계속 필요하다.
