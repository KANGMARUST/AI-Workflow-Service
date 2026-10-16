# Codex 백엔드 개발 환경

## 작업 디렉터리

Codex에서 이 저장소의 `backend/`를 작업 디렉터리로 선택한다. 저장소 루트에서 시작한 세션은 백엔드 수정 전에 `backend/AGENTS.md`를 읽도록 요청한다.

`AGENTS.md`는 작업 규칙이고, 이 문서는 환경 준비와 실행 명령을 설명한다. 기존 Codex 계정·모델·전역 설정은 그대로 사용한다. 아래 환경을 사용하기 위해 별도 Codex CLI나 MCP 서버를 설치할 필요는 없다.

## 최초 준비

Windows PowerShell에서 저장소 루트로 이동한 뒤 실행한다. `uv`가 필요하다.

```powershell
uv venv --python 3.12 backend/.venv
uv pip install --python backend/.venv/Scripts/python.exe -r backend/requirements-dev.txt
if (-not (Test-Path backend/.env)) {
    Copy-Item backend/.env.example backend/.env
}
```

Python 3.12는 Docker와 맞춘 버전이다. 없으면 uv가 다운로드한다. 기존 `.venv`가 있으면 생성 명령을 생략한다. 네트워크나 uv 캐시 접근이 Codex 권한 정책에 막히면 해당 명령에 필요한 승인을 요청한다.

`.env`의 예시 키는 실제 연동용이 아니다. 외부 키가 없으면 로컬 저장·추출·검토·비교·견적 출력이 가능하다. Studio를 사용할 때 `UPSTAGE_API_KEY`와 Agent/Config ID를 설정한다. Supabase 직접 연결에는 `DATABASE_URL`을 사용한다. `.env`와 `.venv/`, `.runtime/`은 Git에서 제외한다. 최신 기능과 전체 API 계약은 `README.md`에 있다.

## 서버 실행

이후 명령은 `backend/`에서 실행한다. 가상환경 활성화 없이 실행 파일을 직접 호출하므로 PowerShell 활성화 스크립트 정책을 변경할 필요가 없다.

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- 헬스 체크: `http://127.0.0.1:8000/health`
- Swagger: `http://127.0.0.1:8000/docs`
- 종료: 실행한 터미널에서 `Ctrl+C`. 백그라운드 작업 때문에 worker는 1개로 유지한다.
- 8000번 포트가 사용 중이면 `--port 8001` 등 다른 포트로 실행한다.

## 기본 검증

`backend/`에서 실행한다.

```powershell
# 설치한 패키지의 의존성 정합성
uv pip check --python .venv/Scripts/python.exe

# 기존 골격의 포맷은 유지하면서 문법과 주요 오류 검사
.\.venv\Scripts\python.exe -m ruff check app --select E9,F63,F7,F82

# 외부 서비스 호출 없이 앱 로딩, 헬스 체크, OpenAPI 생성 확인
@'
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    response = client.get("/health")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok", response.text
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    assert "/api/add" in response.json()["paths"], response.text
print("Health and OpenAPI OK")
'@ | .\.venv\Scripts\python.exe -
```

자동 테스트 44개는 `.\.venv\Scripts\python.exe -m pytest tests -q --basetemp=.runtime/pytest`로 실행한다. 별도 임시 DB·파일 경로를 사용하며 실제 Upstage API는 호출하지 않는다. 외부 API 실검증은 `README.md`의 명시적인 `tools/live_agent_check.py --live` 절차를 따른다.

## Codex 작업 방식

- 작업 지침: `AGENTS.md`
- Python 실행 파일: `backend/.venv/Scripts/python.exe`
- 작업 시작 시 변경 상태를 확인하고 요청에 필요한 파일만 수정한다.
- 검증 결과와 실제 외부 연동 확인 여부를 구분해 전달한다.
- 추가 MCP·스킬·Codex 설정은 필요한 작업이 생기면 구성한다. 프로젝트 설정은 신뢰된 프로젝트에서 로드되며, 세션과 관리 정책에 따라 지원 범위가 달라질 수 있다.

공식 참고: [작업 지침 탐색](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Codex 설정 우선순위](https://learn.chatgpt.com/docs/config-file/config-basic).
