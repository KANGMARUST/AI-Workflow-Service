# 현재 견적 아카이브 프로젝트의 Codex CLI 실행

설정일: 2026-10-14 (한국 시간). 프로젝트: D:\teamgame\AI-Workflow-Service\project.

## 시작

파일 탐색기로 **D:\teamgame\AI-Workflow-Service 저장소 폴더 또는 그 안의 project 폴더**를 열고 주소창에 `cmd`를 입력한다. 열린 CMD에서:

```cmd
codex
```

다른 폴더에서 열었다면:

```cmd
cd /d "D:\teamgame\AI-Workflow-Service"
codex
```

이 폴더의 codex.cmd가 설치된 Codex 실행 파일을 찾아 실행한다. 저장소 루트에서 시작하면 전체 저장소, project에서 시작하면 앱 폴더를 작업 루트로 사용하고 workspace-write/on-request 정책을 사용한다. 기존 계정 인증을 유지한다. 현재 컴퓨터의 Python/Node 경로는 해당 CLI 프로세스에만 준비하며 전역 PATH·실행 정책을 변경하지 않는다.

기존 기본 모델 gpt-6.1-sol은 실제 CLI 실행에서 이 계정 미지원 오류를 반환했다. 이 프로젝트 진입점에서만 gpt-6-sol을 적용하고 앱·전역 모델 설정은 유지한다. CLI의 `/model` 또는 `codex -m 사용가능한모델`로 변경할 수 있다. 환경변수 QUOTE_CODEX_MODEL도 프로젝트 진입점 모델을 지정할 수 있으나 보통 설정할 필요가 없다.

CLI는 AGENTS.md를 자동으로 읽고 README.md, DEVELOPMENT.md, docs/AGENT_WORKFLOW.md를 확인하도록 안내받는다. 이 문서들이 현재 프로젝트 상태를 인계한다. 이전 채팅 전체가 새 세션에 자동 전달된다고 가정하지 않는다.

실행 후 원하는 작업을 입력한다. 예: `현재 구현과 개발 MD를 확인하고 견적 비교 결과 화면을 개선해줘. 기존 원본 금액은 유지해줘.`

## 기존 작업과 도구

Studio 에이전트 3개와 API 연결은 그대로 사용한다. API 키를 CMD 명령이나 시작 파일에 넣지 않는다. 웹 사용자는 API 설정 메뉴에서 자신의 키를 적용한다. 개발자의 허가된 실연결 테스트 방식은 AGENTS.md와 AGENT_WORKFLOW.md에 기록돼 있다.

CLI 안에서 `/mcp`로 도구를 확인한다. 현재 설치 설정에 cua_repl이 활성화돼 있으나 앱·브라우저 연결은 세션에서 확인해야 한다. Studio 조작이 필요하면 Codex 앱과 브라우저 확장을 켠 상태에서 연결을 확인한다. 연결이 없으면 CLI에서 설정 파일·연결 코드를 수정하고 Studio 설정 가져오기를 병행한다.

웹을 이용한 에이전트 구축이 필요하지만 웹 제어에 실패하면, CLI가 그 시점의 목표·스키마·설정 파일·실패 원인·남은 단계·완료 기준을 채운 **GPT Work 전달용 프롬프트**를 제공하도록 AGENTS.md에 설정했다. 사용자는 해당 요청문과 명시된 파일을 GPT Work에 전달하면 된다. 로컬 파일 접근을 가정하지 않으며 API 키는 요청문에 넣지 않는다.

웹 실행은 별도 CMD의 `start.cmd`, 종료는 `stop.cmd`다. 이전 CLI 작업은 `codex resume`에서 해당 프로젝트의 세션을 선택한다.

## 확인 명령

```cmd
codex --version
codex login status
codex mcp list
```

최초 실행에서 로그인 안내가 나오면 기존 ChatGPT 계정으로 진행한다. 이 설정은 인증 파일이나 비밀 키를 복사하지 않는다. 처음 프로젝트 신뢰 안내가 나온다면 경로가 D:\teamgame\AI-Workflow-Service\project인지 확인한다.

설정 파일: 프로젝트 codex.cmd, AGENTS.md, 이 문서. CLI 버전·로그인·루트·지침 읽기 검증 결과는 DEVELOPMENT.md에 기록한다.

## 이번 설정의 검증 결과

- 프로젝트 CMD의 `where codex`가 project/codex.cmd를 우선 선택했다.
- `codex --version`: codex-cli 0.155.1. `codex login status`: 기존 ChatGPT 로그인 정상.
- 첫 읽기 전용 실행은 기존 gpt-6.1-sol 계정/CLI 미지원 오류로 실패했다. 앱 설정은 유지하고 프로젝트 진입점의 gpt-6-sol로 수정한 후 재실행했다.
- 실제 `codex exec` 읽기 전용 검사 성공(종료 코드 0): 프로젝트 루트, 4개 개발 문서, 새 견적 생성 제외 범위, 에이전트 ID 3개, Python 3.12.14·Node v24.19.0 실행을 확인했다. `exec` 확인에는 현재 Git 저장소가 아닌 프로젝트라 --skip-git-repo-check를 사용했다.
- 브라우저 조작이나 Upstage API 호출은 이번 CLI 설정 검사에서 실행하지 않았다. 브라우저 도구 활성 설정은 확인했지만 실제 CLI 브라우저 연결은 미검증이다.
- 모델·전역 환경·기존 DB·원본·서버 상태는 변경하지 않았다. 프로젝트 진입점의 모델 지정만 추가했다.

공식 지침: https://learn.chatgpt.com/docs/agent-configuration/agents-md , https://learn.chatgpt.com/docs/codex/cli

## 새 GitHub 작업 폴더로 인계 (2026-10-14)

현재 저장소 및 루트 CMD의 CLI 작업 경로는 D:\teamgame\AI-Workflow-Service이고 앱 소스는 그 안의 project다. 저장소 루트에서 codex/start/stop/setup 명령을 입력해도 project의 기존 진입점으로 연결된다. Git root의 AGENTS.md와 project/AGENTS.md를 함께 읽어 기존 아카이브 범위와 GPT Work 전달 지침을 인계한다.

라이브러리와 로컬 데이터가 이미 이 checkout에 있다. 환경 설정은 원본·DB·사용자 미커밋 변경·전역 모델/계정 설정을 초기화하지 않는다. 이미 사용 중인 5173/8000 포트의 서버는 소유 경로를 확인하고 새 checkout의 서버와 혼동하지 않는다.

필요한 실연결 테스트 키를 새 저장소에 복사하지 않는다. 기존 개인 키의 위치는 이전 checkout 기준이므로 새 위치에서 테스트 키가 자동 제공된다고 가정하지 않는다. 웹 사용자는 본인 API를 직접 입력한다.

저장소 루트의 진입점은 QUOTE_CODEX_WORKSPACE를 해당 CMD 프로세스에만 지정해 Git 작업과 루트 지침을 함께 사용할 수 있게 한다. 이 변수나 PATH를 전역으로 저장하지 않는다.

## Windows 명령 실행 오류 해결

새 위치의 실제 CLI 검사에서 기존 elevated sandbox의 helper_unknown_error/setup refresh had errors가 발생했다. CLI 0.162.1에서 공식 MXC 검사 명령은 MXC_OK(종료 0)를 반환했다. 따라서 새 저장소의 project/codex.cmd에서만 windows.sandbox=mxc를 적용한다. 전역 설정이나 보호를 끄는 옵션은 사용하지 않는다.

웹 서버는 별도 일반 CMD에서 start.cmd를 실행한다. MXC 내부의 명령에서 분리 실행한 서버는 명령 종료와 함께 정리될 수 있다. 현재 5173/8000 개발 서버는 이전 D:\workflow AI hacker\project 소유로 확인되었으며 이번 설정에서 중지하거나 교체하지 않았다. 새 폴더의 웹을 실행하려면 이전 폴더의 stop.cmd로 해당 서버를 정상 종료한 뒤 새 저장소의 start.cmd를 실행한다.

공식 설명: https://learn.chatgpt.com/docs/windows/windows-sandbox

## 새 저장소에서 최종 확인한 항목

- CLI 0.162.1, 기존 ChatGPT 로그인, 저장소 루트의 codex 진입점 정상.
- MXC 적용 후 실제 CLI 명령 실행 성공. Git 루트와 작업 루트는 D:\teamgame\AI-Workflow-Service.
- 루트 및 project/AGENTS.md 읽기, GPT Work 대체 프롬프트 지침 인계 확인.
- Python 3.12.14·Node v24.19.0 실행, 백엔드 의존성과 모듈 10개 문법, 현재 프론트 빌드 통과.
- workspace 권한에서 임시 파일 생성·제거 확인. 기존 변경·원본·DB는 보존.
- 이 checkout의 MXC 설정은 Codex CLI 0.162 이상이 필요하다. 모델·격리 방식의 전역 설정은 변경하지 않는다.

```cmd
cd /d "D:\teamgame\AI-Workflow-Service"
codex
```
