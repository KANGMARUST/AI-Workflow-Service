# 기존 견적 아카이브 통합 검증

최신 사용자 정정과 `DEVELOPMENT.md`를 기준으로 **이미 발행된 견적의 등록·보존·정정·검색·상세·원본 조회**를 검증한다. 새 견적 작성·가격 재계산·옵션 선택·출력 양식은 요구하지 않으며 해당 API가 비활성화되었는지 확인한다. 과거 생성 워크플로 테스트는 `archive/generated-workflow-before-scope-correction.py`에 이력으로만 보존했다.

프로젝트 루트에서 실행:

```powershell
python tests/test_integration.py
```

이 환경의 번들 Python:

```powershell
& 'C:\Users\gns03\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests/test_integration.py
```

백엔드 의존성의 `backend/.packages` 경로는 자동 인식한다. 테스트는 `tests/.runs` 아래에 임시 SQLite와 파일 저장소를 생성하고 별도 포트의 실제 HTTP API 서버를 실행한다. 사용자가 등록한 기존 DB·원본 파일은 변경하지 않는다. 실행 후 임시 서버와 해당 실행 폴더를 정리한다. 외부 AI 연결은 비활성화한다.

검증 항목:

- 실제 PDF2·XLS1 등록, 중복 파일 및 원본 파일 동일성
- 16M·266.74M 공급가액, VAT 별도 세율·세액·세금 포함 총액의 null 유지
- 5패키지·15부품 관계 및 XLS의 대체 옵션 3품목 전체 보존, 합계 미기재 유지
- XLSX·DOCX·한국어 로컬 OCR, 부분 실패 및 빈 파일
- 추출 정정 시 수량·단가·금액 자동 덮어쓰기 금지, 계산 검사 값 분리 및 정정 이력
- 담당자·연락처·제목·품목·기간 조합 필터 및 자연어 검색
- 모든 원본 옵션·부품·검토 중 문서의 품목 이력 조회
- 생성·복사·수주 상태·견적 출력·양식 관리 API 차단
- 과거 생성·복사 자료 DB 보존 및 아카이브 검색·통계 제외
- 아카이브 현황, 원본 접근 경로 보호, 재시작 후 저장 유지
- 구버전의 추정 10%·17.6M 보정, 실제 원본 값 ledger와 사용자 정정·과거 이력의 분리 보존

최종 결과는 `integration-results.json`에 현재 아카이브 범위를 명시해 기록한다. `tests/qa`의 과거 출력 렌더는 범위 정정 전 검증 이력이며 현재 제품 기능이나 최신 합격 기준으로 사용하지 않는다. 브라우저 UI, 외부 AI 및 PostgreSQL 연결은 별도 검증 대상이다.
