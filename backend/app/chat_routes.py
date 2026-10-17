from fastapi import APIRouter, Query, Request

from .chat_schemas import ChatCreate, ChatSend, ChatUpdate

router = APIRouter(prefix="/chats", tags=["견적서 대화"])


@router.post("", status_code=201, summary="선택한 견적서로 대화 시작")
def create_chat(request: Request, payload: ChatCreate):
    return request.app.state.chat.create(payload)


@router.get("", summary="활성 견적서의 대화 목록")
def list_chats(request: Request, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return request.app.state.chat.list(limit, offset)


@router.get("/models", summary="사용자가 선택할 수 있는 대화 모델")
def list_models(request: Request):
    return request.app.state.chat.models()


@router.get("/usage", summary="저장된 전체 대화 답변의 토큰 사용량")
def total_usage(request: Request):
    return request.app.state.chat.usage()


@router.get("/{chat_id}", summary="대화 정보·모델·버전·누적 사용량 조회")
def get_chat(request: Request, chat_id: str):
    return request.app.state.chat.get(chat_id)


@router.patch("/{chat_id}", summary="대화 모델 변경")
def update_chat(request: Request, chat_id: str, payload: ChatUpdate):
    return request.app.state.chat.update(chat_id, payload)


@router.get("/{chat_id}/usage", summary="대화별·모델별 누적 토큰 사용량")
def chat_usage(request: Request, chat_id: str):
    return request.app.state.chat.usage(chat_id)


@router.get("/{chat_id}/messages", summary="질문·답변·견적 근거 이력")
def get_messages(request: Request, chat_id: str, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return request.app.state.chat.messages(chat_id, limit, offset)


@router.post("/{chat_id}/messages", status_code=201, summary="이전 대화를 이어서 질문·답변 저장")
def send_message(request: Request, chat_id: str, payload: ChatSend):
    return request.app.state.chat.send(chat_id, payload)


@router.delete("/{chat_id}", summary="견적서 대화와 메시지 영구 삭제")
def delete_chat(request: Request, chat_id: str):
    return request.app.state.chat.delete(chat_id)
