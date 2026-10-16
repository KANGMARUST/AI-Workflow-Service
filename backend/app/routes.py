from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select

from .database import Job, Quote, Revision, now
from .documents import quote_pdf, quote_xlsx
from .domain import compare_quotes
from .repository import check_version, clean_fields, detail, ensure_idle, record, require, search, set_fields
from .schemas import AgentRequest, CompareRequest, ExtractionRequest, QuoteEditRequest, QuoteListResponse, QuoteSearchRequest, QuoteStatus, QuoteStatusRequest

router = APIRouter()


def svc(request):
    return request.app.state.service


@router.post("/add", status_code=201, summary="견적서 원본 등록")
async def add_quote(request: Request, file: UploadFile = File(...)):
    service = svc(request)
    try:
        content = await file.read(service.config.max_upload_mb*1024*1024+1)
        return service.upload(content, file.filename)
    finally:
        await file.close()


@router.get("/extract", summary="추출 결과 조회")
def extraction_result(request: Request, quote_id: str = Query(...)):
    with svc(request).db.sessions() as session:
        q = require(session, quote_id)
        job = session.scalar(select(Job).where(Job.quote_id == q.id, Job.kind == "extract").order_by(Job.created_at.desc()).limit(1))
        return {"quote_id": q.id, "extraction_status": q.extraction_status, "extracted_fields": clean_fields(q), "warnings": q.extraction_raw.get("warnings", []), "validation": detail(q)["validation"], "provider": q.extraction_raw.get("provider"), "source_text": q.extraction_raw.get("text"), "source_fields": q.extraction_raw.get("fields"), "latest_job": svc(request).job_data(job) if job else None}


@router.post("/extract", status_code=202, summary="추출 시작")
@router.post("/extraction-jobs", status_code=202, summary="추출 작업 시작")
def start_extract(request: Request, payload: ExtractionRequest, background: BackgroundTasks):
    service = svc(request)
    result = service.start_extraction(payload)
    background.add_task(service.run_extraction, result["job_id"])
    return result


@router.get("/jobs/{job_id}", summary="작업 상태·결과 조회")
def get_job(request: Request, job_id: str):
    with svc(request).db.sessions() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(404, "작업을 찾을 수 없습니다.")
        return svc(request).job_data(job)


@router.post("/search", response_model=QuoteListResponse, summary="복합 조건 검색")
def search_quotes(request: Request, payload: QuoteSearchRequest):
    with svc(request).db.sessions() as session:
        return search(session, payload)


@router.get("/search", response_model=QuoteListResponse, summary="키워드 검색")
def search_get(request: Request, keyword: str = Query(..., min_length=1, max_length=200), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return search_quotes(request, QuoteSearchRequest(keyword=keyword, limit=limit, offset=offset))


@router.get("/cards", response_model=QuoteListResponse, summary="견적서 목록")
def get_cards(request: Request, status: QuoteStatus | None = None, kind: Literal["archive", "draft"] | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return search_quotes(request, QuoteSearchRequest(status=status, kind=kind, limit=limit, offset=offset))


@router.get("/quotes/{quote_id}", summary="상세·품목·검토 오류 조회")
def get_quote(request: Request, quote_id: str):
    with svc(request).db.sessions() as session:
        return detail(require(session, quote_id))


@router.get("/quotes/{quote_id}/source", summary="원본 파일 다운로드")
def get_source(request: Request, quote_id: str):
    service = svc(request)
    with service.db.sessions() as session:
        q = require(session, quote_id)
        path = service.source(q)
        return FileResponse(path, filename=q.source_filename or path.name, headers={"X-Content-Type-Options": "nosniff"})


@router.patch("/edit/{quote_id}", summary="견적서·품목 수정")
@router.patch("/quotes/{quote_id}", summary="견적서·품목 수정")
def edit_quote(request: Request, quote_id: str, payload: QuoteEditRequest):
    with svc(request).db.sessions.begin() as session:
        q = require(session, quote_id)
        ensure_idle(q)
        check_version(q, payload.expected_version)
        changes = payload.model_dump(mode="json", exclude_unset=True, exclude={"expected_version"})
        if changes:
            data = clean_fields(q)
            data.update(changes)
            data["items"], data["raw_fields"] = data.get("items") or [], data.get("raw_fields") or {}
            set_fields(q, data)
            q.status = "review_required"
            record(session, q, "edit")
        return {**detail(q), "updated": bool(changes)}


@router.get("/status/{quote_id}", summary="검토 상태 조회")
def get_status(request: Request, quote_id: str):
    with svc(request).db.sessions() as session:
        q = require(session, quote_id)
        return {"quote_id": q.id, "status": q.status, "version": q.version}


@router.post("/status/{quote_id}", summary="검토 상태 변경")
def update_status(request: Request, quote_id: str, payload: QuoteStatusRequest):
    if payload.status == QuoteStatus.extracting:
        raise HTTPException(409, "extracting은 추출 작업 API에서 설정합니다.")
    with svc(request).db.sessions.begin() as session:
        q = require(session, quote_id)
        ensure_idle(q)
        check_version(q, payload.expected_version)
        q.status, q.updated_at = payload.status.value, now()
        if "note" in payload.model_fields_set:
            q.payload = {**q.payload, "review_note": payload.note}
        record(session, q, "status")
        return {**detail(q), "updated": True}


@router.get("/quotes/{quote_id}/history", summary="수정 이력 조회")
def history(request: Request, quote_id: str, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    with svc(request).db.sessions() as session:
        require(session, quote_id)
        rows = session.scalars(select(Revision).where(Revision.quote_id == quote_id).order_by(Revision.version.desc(), Revision.created_at.desc())).all()
        return {"items": [{"version": r.version, "action": r.action, "created_at": r.created_at, "snapshot": r.snapshot} for r in rows[offset:offset+limit]], "total": len(rows), "limit": limit, "offset": offset}


@router.get("/quotes/{quote_id}/jobs", summary="견적서 작업 이력 조회")
def quote_jobs(request: Request, quote_id: str, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    service = svc(request)
    with service.db.sessions() as session:
        require(session, quote_id)
        jobs = session.scalars(select(Job).where(Job.quote_id == quote_id).order_by(Job.created_at.desc())).all()
        return {"items": [service.job_data(j) for j in jobs[offset:offset+limit]], "total": len(jobs), "limit": limit, "offset": offset}


@router.delete("/quotes/{quote_id}", summary="견적서를 휴지통으로 이동")
def trash_quote(request: Request, quote_id: str):
    with svc(request).db.sessions.begin() as session:
        q = require(session, quote_id)
        ensure_idle(q)
        q.deleted_at, q.updated_at = now(), now()
        record(session, q, "trash")
        return {"quote_id": q.id, "deleted": True, "recoverable": True}


@router.get("/trash", response_model=QuoteListResponse, summary="휴지통 조회")
def trash_list(request: Request, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    with svc(request).db.sessions() as session:
        return search(session, QuoteSearchRequest(limit=limit, offset=offset), trash=True)


@router.post("/quotes/{quote_id}/restore", summary="견적서 복원")
def restore(request: Request, quote_id: str):
    with svc(request).db.sessions.begin() as session:
        q = require(session, quote_id, deleted=True)
        if q.deleted_at:
            q.deleted_at, q.updated_at = None, now()
            record(session, q, "restore")
        return detail(q)


@router.get("/items/history", summary="품목 단가 이력")
def item_history(request: Request, keyword: str | None = Query(None, min_length=1, max_length=200), limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    from .domain import normalized
    with svc(request).db.sessions() as session:
        rows = []
        for q in session.scalars(select(Quote).where(Quote.deleted_at.is_(None)).order_by(Quote.created_at.desc())):
            for item in q.items:
                if not keyword or normalized(keyword) in normalized(item.item_name):
                    rows.append({**item.payload, "quote_id": q.id, "item_id": item.id, "line_number": item.line_number, **{k: q.payload.get(k) for k in ("customer_name", "issue_date", "payment_terms", "delivery_terms", "discount_terms", "tax_rate")}, "currency": item.payload.get("currency") or q.payload.get("currency"), "status": q.status, "kind": q.kind})
        return {"items": rows[offset:offset+limit], "total": len(rows), "limit": limit, "offset": offset}


@router.post("/compare", summary="정확한 숫자 계산 기반 조건별 단가 비교")
def compare(request: Request, payload: CompareRequest):
    with svc(request).db.sessions() as session:
        quotes = []
        for identifier in payload.quote_ids:
            q = require(session, identifier)
            ensure_idle(q)
            quotes.append(detail(q))
        return compare_quotes(quotes, payload.item_name)


@router.get("/quotes/{quote_id}/export", summary="지정 양식 PDF·Excel 출력")
def export(request: Request, quote_id: str, format: Literal["pdf", "xlsx"] = "pdf"):
    service = svc(request)
    with service.db.sessions() as session:
        q = detail(require(session, quote_id))
    if format == "pdf":
        content, media = quote_pdf(q, service.config.pdf_font_path), "application/pdf"
    else:
        content, media = quote_xlsx(q), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="quote-{quote_id}.{format}"', "X-Content-Type-Options": "nosniff"})


@router.post("/agent-runs", status_code=202, summary="Studio 비교 작업")
def agent_run(request: Request, payload: AgentRequest, background: BackgroundTasks):
    service = svc(request)
    result = service.start_agent(payload)
    background.add_task(service.run_agent, result["job_id"])
    return result


@router.get("/stats", summary="견적·검토·거래처·품목 현황")
def stats(request: Request):
    with svc(request).db.sessions() as session:
        quotes = session.scalars(select(Quote).where(Quote.deleted_at.is_(None))).all()
        return {"document_count": sum(q.kind == "archive" for q in quotes), "review_required_count": sum(q.status == "review_required" for q in quotes), "confirmed_count": sum(q.status == "confirmed" for q in quotes), "customer_count": len({q.payload.get("customer_name") for q in quotes if q.payload.get("customer_name")}), "item_count": sum(len(q.items) for q in quotes)}


@router.get("/capabilities", summary="프론트 연결용 지원 기능·설정 상태")
def capabilities(request: Request):
    config = svc(request).config
    return {"supported_extensions": [".xls", ".xlsx", ".pdf"], "max_upload_mb": config.max_upload_mb, "max_document_pages": config.max_document_pages, "upstage_configured": bool(config.upstage_api_key.get_secret_value()) and not config.upstage_api_key.get_secret_value().startswith("replace-"), "database": svc(request).db.engine.dialect.name, "statuses": [s.value for s in QuoteStatus], "authentication_required": bool(config.api_token.get_secret_value())}
