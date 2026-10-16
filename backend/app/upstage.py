import json
import time

import httpx

from .config import Settings


class AgentError(ValueError):
    pass


class UpstageClient:
    def __init__(self, config: Settings, transport=None):
        self.config = config
        self.transport = transport

    def run(self, pdf: bytes, agent_id: str, config_id: str):
        key = self.config.upstage_api_key.get_secret_value()
        if not key or key.startswith("replace-"):
            raise AgentError("Upstage API 키가 설정되지 않았습니다.")
        started = time.monotonic()
        file_id = None
        envelope = None
        with httpx.Client(base_url=self.config.upstage_base_url.rstrip("/")+"/", headers={"Authorization": f"Bearer {key}"}, timeout=30, transport=self.transport) as client:
            try:
                uploaded = self._json(client.post("files", files={"file": ("quoteflow-input.pdf", pdf, "application/pdf")}, data={"purpose": "user_data"}))
                file_id = uploaded.get("id")
                if not isinstance(file_id, str) or not file_id:
                    raise AgentError("Upstage 파일 ID가 없습니다.")
                response = self._json(client.post("responses", json={"model": agent_id, "config_id": config_id, "include": ["last"], "input": [{"role": "user", "content": [{"type": "input_file", "file_id": file_id}]}]}))
                remote_id = response.get("id")
                if not isinstance(remote_id, str) or not remote_id:
                    raise AgentError("Upstage 작업 ID가 없습니다.")
                while response.get("status") in ("queued", "in_progress"):
                    if time.monotonic()-started >= self.config.agent_timeout_seconds:
                        raise AgentError("Upstage 작업 제한 시간을 초과했습니다. 나중에 재시도하세요.")
                    time.sleep(self.config.agent_poll_seconds)
                    raw = client.get(f"responses/{remote_id}", params={"include": "last"})
                    if raw.status_code in (429, 500, 502, 503, 504):
                        continue
                    response = self._json(raw)
                if response.get("status") != "completed":
                    raise AgentError("Upstage 작업이 실패 또는 취소되었습니다. Studio의 입력 문서와 설정을 확인하세요.")
                value = response.get("output_text")
                if not value:
                    texts = [c.get("text", "") for o in response.get("output", []) if o.get("type") == "message" for c in o.get("content", []) if c.get("type") == "output_text"]
                    value = texts[-1] if texts else None
                if not isinstance(value, str):
                    raise AgentError("Upstage 작업에 JSON 출력이 없습니다.")
                value = value.strip()
                if value.startswith("```json") and value.endswith("```"):
                    value = value[7:-3].strip()
                result = json.loads(value)
                if not isinstance(result, dict):
                    raise AgentError("Upstage 출력이 JSON 객체가 아닙니다.")
                envelope = {"data": result, "remote_job_id": remote_id, "agent_id": agent_id, "config_id": config_id}
                return envelope
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                raise AgentError("Upstage 통신 또는 JSON 응답 오류입니다. 인증·네트워크·설정을 확인하세요.") from exc
            finally:
                if file_id:
                    try:
                        cleanup = client.delete(f"files/{file_id}").is_success
                    except httpx.HTTPError:
                        cleanup = False
                    if envelope is not None:
                        envelope["input_file_deleted"] = cleanup

    @staticmethod
    def _json(response):
        if not response.is_success:
            raise AgentError(f"Upstage 요청이 거절되었습니다 (HTTP {response.status_code}). 인증·에이전트 접근 권한·호출 한도를 확인하세요.")
        return response.json()
