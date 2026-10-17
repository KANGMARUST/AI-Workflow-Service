import httpx
from pydantic import ValidationError

from .chat_schemas import ChatAnswer


class ChatError(ValueError):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


class SolarChatClient:
    def __init__(self, config, transport=None):
        self.config, self.transport = config, transport

    def complete(self, messages, citation_fields, model=None):
        requested_model = model or self.config.chat_model
        key = self.config.upstage_api_key.get_secret_value()
        if not key or key.startswith("replace-"):
            raise ChatError("견적 대화에는 UPSTAGE_API_KEY 설정이 필요합니다.", 503)
        schema = ChatAnswer.model_json_schema()
        properties = schema["$defs"]["ChatCitation"]["properties"]
        properties["quote_id"]["enum"] = list(citation_fields)
        properties["field_path"]["enum"] = sorted({p for paths in citation_fields.values() for p in paths})
        try:
            with httpx.Client(base_url=self.config.chat_base_url.rstrip("/") + "/",
                              headers={"Authorization": f"Bearer {key}"},
                              timeout=self.config.chat_timeout_seconds, transport=self.transport) as client:
                response = client.post("chat/completions", json={
                    "model": requested_model, "messages": messages,
                    "temperature": 0.2, "max_tokens": self.config.chat_max_tokens,
                    "stream": False,
                    "response_format": {"type": "json_schema", "json_schema": {
                        "name": "quote_chat_answer", "strict": True, "schema": schema,
                    }},
                })
        except httpx.TimeoutException as exc:
            raise ChatError("AI 답변 시간이 초과되었습니다. 대화를 다시 조회한 뒤 재시도하세요.", 504) from exc
        except httpx.HTTPError as exc:
            raise ChatError("AI 대화 서비스에 연결하지 못했습니다. 잠시 후 다시 시도하세요.") from exc
        if response.status_code in (401, 403, 404):
            raise ChatError("AI 대화 인증 또는 모델 설정을 확인하세요.", 503)
        if response.status_code == 429:
            raise ChatError("AI 대화 호출 한도에 도달했습니다. 잠시 후 다시 시도하세요.", 503)
        if not response.is_success:
            raise ChatError("AI 대화 요청을 처리하지 못했습니다. 잠시 후 다시 시도하세요.")
        try:
            payload = response.json()
            choice = payload["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ChatError("AI 답변이 완성되지 않았습니다. 질문 범위를 줄여 다시 시도하세요.")
            answer = ChatAnswer.model_validate_json(choice["message"]["content"])
            usage = payload.get("usage") or {}
            usage = {k: v for k, v in usage.items() if k in ("prompt_tokens", "completion_tokens", "total_tokens") and type(v) is int and v >= 0}
            model = payload.get("model") or requested_model
            if not isinstance(model, str) or len(model) > 200:
                raise ValueError("Invalid model")
            return answer, {"model": model, "requested_model": requested_model, "usage": usage}
        except ChatError:
            raise
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, ValidationError) as exc:
            raise ChatError("AI 대화 응답 형식이 올바르지 않습니다. 다시 시도하세요.") from exc
