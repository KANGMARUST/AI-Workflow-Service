from pydantic import Field, model_validator

from .schemas import InputModel


class ChatCreate(InputModel):
    quote_ids: list[str] = Field(min_length=1, max_length=5)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    model: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_quotes(self):
        if len(set(self.quote_ids)) != len(self.quote_ids):
            raise ValueError("견적 ID가 중복되었습니다.")
        return self


class ChatUpdate(InputModel):
    model: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=1)


class ChatSend(InputModel):
    content: str = Field(min_length=1, max_length=4000)
    expected_version: int = Field(ge=1)


class ChatCitation(InputModel):
    quote_id: str = Field(min_length=1, max_length=36)
    field_path: str = Field(min_length=1, max_length=200, pattern=r"^[a-z_]+(?:\.(?:[a-z_]+|\d+))*$")


class ChatAnswer(InputModel):
    answer: str = Field(min_length=1, max_length=12000)
    citations: list[ChatCitation] = Field(max_length=20)
    insufficient_data: bool
