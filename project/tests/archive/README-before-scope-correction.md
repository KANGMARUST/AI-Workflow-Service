# API 통합 검증

`test_integration.py`는 실제 HTTP 서버를 별도 포트로 시작하고 표준 `unittest`와 `urllib`로 업무 흐름을 검증합니다. 새 임시 디렉터리를 `QUOTE_DATA_DIR`로 설정하므로 사용자가 등록한 견적 DB와 원본 저장소는 변경하지 않습니다. `project/data`의 샘플 파일은 읽기만 합니다. 원격 AI 및 외부 데이터베이스 연결은 테스트 환경에서 비활성화됩니다.

프로젝트 루트에서 백엔드 의존성이 있는 Python으로 실행합니다.

```powershell
python tests/test_integration.py
```

이 환경의 번들 Python을 사용하는 경우:

```powershell
& 'C:\Users\gns03\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests/test_integration.py
```

백엔드 의존성이 `backend/.packages`에 설치되어 있으면 자동으로 해당 위치를 사용합니다. XLSX/DOCX/PNG fixture 생성 및 출력 검증에 `openpyxl`, `python-docx`, `Pillow`, `pdfplumber`, `pypdfium2`가 필요합니다. PNG 검증은 모의 응답 없이 설치된 로컬 OCR을 실행합니다.

검증 항목:

- 실제 PDF 2개와 XLS 등록, 금액·품목·패키지 구성 및 선택 옵션
- 원본 보관, 중복 업로드, 서로 다른 형식 입력과 부분 실패
- 실제 PNG OCR 및 XLSX/DOCX 구조 추출
- 검토 전 출력 차단, 오류 확정 차단, 인정 가능한 경고 확인
- 복사 후 수량 변경, 금액 재계산, 버전 이력, Excel/PDF 출력 내용
- 소수 계산, 할인·부가세, 패키지 세부 항목의 이중 합산 방지
- 검색 필터, 비교 조건 유지, 자연어 검색, 수주 상태 및 통계
- 사용자 XLSX 템플릿 치환 및 품목 출력
- 표준·간편 PDF 양식의 실제 차이, 사용자 템플릿 제목·placeholder·품목의 PDF 반영
- 경로 순회 차단 및 서버 재시작 후 데이터 유지
- 80개 품목의 여러 페이지 PDF 출력, 한국어 조건·모든 품목 포함 및 첫/마지막 페이지 렌더
- 외화 견적을 원화 합계에 합산하지 않고 통화별로 분리하는 통계
- 클라이언트의 `review_status=confirmed` 위조 및 확정 후 음수 변조의 출력 우회 차단

실행 후 `integration-results.json`에 통과 여부와 테스트별 결과를 저장합니다. 정상 완료 시 임시 데이터와 서버는 정리됩니다. 외부 AI, PostgreSQL/Supabase의 실제 연결과 브라우저 UI는 별도 검증 대상입니다.
