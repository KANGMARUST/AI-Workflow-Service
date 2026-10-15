from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from .schemas import QuoteListResponse, QuoteSearchRequest, QuoteEditRequest, QuoteStatusRequest
router=APIRouter()
@router.post("/add",summary="견적서 등록")
async def add_quote(file: UploadFile=File(...)):
    if not file.filename: raise HTTPException(400,"파일명이 필요합니다.")
    return {"quote_id":"stub-quote-id","status":"review_required","message":"스텁 응답: 실제 업로드 미구현"}
@router.get("/extract",summary="문서 추출 결과 조회")
async def extract_quote(quote_id: str=Query(...)):
    return {"quote_id":quote_id,"extraction_status":"not_implemented","extracted_fields":{},"warnings":["Upstage 추출 연동 전"]}
@router.post("/search",response_model=QuoteListResponse,summary="복합 검색")
async def search_quotes(payload: QuoteSearchRequest):
    return QuoteListResponse(items=[],total=0,limit=payload.limit,offset=payload.offset)
@router.get("/search",response_model=QuoteListResponse,summary="키워드 검색")
async def search_quotes_get(keyword: str=Query(...,min_length=1),limit: int=Query(20,ge=1,le=100),offset: int=Query(0,ge=0)):
    return QuoteListResponse(items=[],total=0,limit=limit,offset=offset)
@router.get("/cards",response_model=QuoteListResponse,summary="견적서 목록")
async def get_cards(status: str|None=None,limit: int=Query(20,ge=1,le=100),offset: int=Query(0,ge=0)):
    return QuoteListResponse(items=[],total=0,limit=limit,offset=offset)
@router.patch("/edit/{quote_id}",summary="견적서 수정")
async def edit_quote(quote_id: str,payload: QuoteEditRequest):
    return {"quote_id":quote_id,"updated":False,"message":"Not implemented"}
@router.get("/status/{quote_id}",summary="상태 조회")
async def get_status(quote_id: str):
    return {"quote_id":quote_id,"status":"review_required"}
@router.post("/status/{quote_id}",summary="상태 변경")
async def update_status(quote_id: str,payload: QuoteStatusRequest):
    return {"quote_id":quote_id,"status":payload.status,"updated":False}
