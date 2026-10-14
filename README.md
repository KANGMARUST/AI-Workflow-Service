# AI-Workflow-Service

기존 견적서를 보관·추출·정정·검색하고 Upstage Studio 에이전트로 검토·비교하는 프로젝트입니다. 앱 소스는 [project](project)에 있습니다.

## Codex CLI 개발

이 저장소 폴더에서 CMD를 열고:

```cmd
codex
```

루트의 진입 파일이 project 폴더의 CLI 설정과 작업 지침을 연결합니다. 기존 변경과 개발 기록을 확인한 뒤 원하는 작업을 요청하세요.

- [프로젝트 개발 지침](project/AGENTS.md)
- [CLI 실행 안내](project/docs/CLI_SETUP.md)
- [개발 기록](project/DEVELOPMENT.md)
- [에이전트·API 기록](project/docs/AGENT_WORKFLOW.md)
- [앱 소개·설치](project/README.md)

웹 시작은 `start.cmd`, 종료는 `stop.cmd`, 새 컴퓨터 의존성 설치는 `setup.cmd`입니다. 웹 주소는 http://127.0.0.1:5173 입니다. API 키는 웹의 사용자 API 설정에서 입력합니다.
