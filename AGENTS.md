# AI-Workflow-Service 저장소 작업 지침

현재 GitHub 작업 저장소는 이 폴더이며 앱 소스는 `project/`에 있다. 저장소 루트와 project 폴더 모두에서 CLI 개발을 이어갈 수 있다. 루트 codex.cmd는 project/codex.cmd로 연결하되 작업 루트는 이 Git 저장소 전체로 설정하고 해당 모델·런타임을 적용한다. project 폴더에서 직접 codex를 실행하면 앱 폴더에 집중한다.

작업 전에 `project/AGENTS.md` 및 그 문서가 지정한 개발 기록을 읽는다. 최신 작업 기준은 `project/DEVELOPMENT.md`, 에이전트/API 구성은 `project/docs/AGENT_WORKFLOW.md`, 실행 안내는 `project/docs/CLI_SETUP.md`다. 이전 경로의 복사본보다 **이 Git checkout의 현재 파일과 최근 기록**을 기준으로 작업한다.

기존 견적 아카이브 제품 범위를 유지하고 새 견적 작성·복사·가격 산정·출력 기능을 추가하지 않는다. 원본·DB·정정 이력·미기재 값·모든 옵션 보존 규칙은 project/AGENTS.md를 따른다. 에이전트 웹 제어에 실패하면 GPT Work에 전달할 실제 작업 프롬프트를 제공한다.

이 checkout에는 이미 사용자의 미커밋 변경이 있다. 먼저 Git 상태를 확인하고 기존 수정·삭제·미추적 파일을 덮어쓰거나 되돌리지 않는다. 다른 원본 폴더로 자동 동기화하거나 reset/clean/강제 pull을 실행하지 않는다. 커밋·푸시는 사용자가 요청한 범위에서 진행한다. API 키와 인증값을 Git·로그·MD에 남기지 않는다.

Input_data는 사용자 원본, Test_input_data는 가상 테스트 자료다. 실제 회사 원본을 외부 API 테스트에 사용하지 않는다. 현재 데이터 파일이나 이미 추적 중인 자료를 환경 설정 과정에서 제거하지 않는다. private 키 파일을 새 저장소에 복사하지 않는다.

루트 CMD: `codex`는 개발 시작, `start.cmd`는 웹 시작, `stop.cmd`는 해당 프로젝트 서버 종료, `setup.cmd`는 의존성 설치다. 기존 다른 경로의 개발 서버가 같은 포트를 사용하면 기존 서버를 자동 종료하지 말고 소유 경로를 확인한 뒤 안내한다.

## 이 checkout의 Windows CLI

설치된 CLI 0.162.1의 기존 elevated 격리 환경이 setup refresh 오류를 반환하여, 이 checkout 진입점에서만 공식 권장 MXC를 사용한다. 호환성 검사에서 MXC_OK와 종료 코드 0을 확인했다. workspace-write/on-request 보호를 유지하고 전역 설정·계정·방화벽·Windows 사용자·Defender 보호를 변경하지 않는다.

MXC의 명령 종료 시 하위 프로세스가 정리될 수 있으므로 **개발 웹 서버는 사용자가 별도 CMD에서 루트 start.cmd를 실행하는 방식**을 안내한다. 다른 checkout의 서버를 새 checkout 서버로 표시하지 않는다. CLI에서 시작한 서버가 명령 종료 후에도 실제로 응답하는지 확인하지 않았다면 실행 완료로 기록하지 않는다.
