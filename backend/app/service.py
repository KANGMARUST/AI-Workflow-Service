import copy
import hashlib
import os
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .database import Job, Quote, now, uid
from .documents import DocumentError, agent_input, local_extract, make_pdf, read_document, validate_file
from .domain import calculate_draft, compare_quotes, parse_json_field
from .extraction import normalize_result
from .repository import check_version, clean_fields, detail, ensure_idle, record, require, set_fields
from .schemas import DraftRequest, QuoteFields
from .upstage import AgentError, UpstageClient


class Service:
    def __init__(self, config, db):
        self.config, self.db = config, db
        self.files = config.data_dir / "files"
        self.files.mkdir(parents=True, exist_ok=True)
        self.agent = UpstageClient(config)

    def upload(self, data, filename):
        if not filename or any(x in filename for x in ("/", "\\")) or any(ord(x) < 32 or ord(x) == 127 for x in filename) or len(filename) > 240:
            raise HTTPException(400, "안전한 파일명이 필요합니다. 경로는 포함할 수 없습니다.")
        suffix = Path(filename).suffix.lower()
        if len(data) > self.config.max_upload_mb*1024*1024:
            raise HTTPException(413, "업로드 크기 제한을 초과했습니다.")
        if not data:
            raise HTTPException(400, "빈 파일은 등록할 수 없습니다.")
        try:
            validate_file(data, suffix, self.config.max_document_pages)
        except DocumentError as exc:
            raise HTTPException(422, str(exc)) from exc
        digest = hashlib.sha256(data).hexdigest()
        with self.db.sessions() as session:
            old = session.scalar(select(Quote).where(Quote.source_hash == digest))
            if old:
                if old.deleted_at:
                    raise HTTPException(409, "휴지통에 같은 원본이 있습니다. 먼저 복원하세요.")
                return {**detail(old), "duplicate": True}
        path = self.files / (digest + suffix)
        temporary = self.files / (uid() + ".tmp")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, path)
            with self.db.sessions.begin() as session:
                quote = Quote(id=uid(), source_filename=filename, source_storage_path=path.name, source_hash=digest)
                set_fields(quote, QuoteFields().model_dump(mode="json"))
                session.add(quote)
                record(session, quote, "upload")
                result = {**detail(quote), "duplicate": False}
            return result
        except IntegrityError:
            # Another request may have registered the exact same content concurrently.
            with self.db.sessions() as session:
                old = session.scalar(select(Quote).where(Quote.source_hash == digest))
                if old and not old.deleted_at:
                    return {**detail(old), "duplicate": True}
            raise HTTPException(409, "같은 원본 등록이 충돌했습니다. 다시 조회하세요.")
        finally:
            temporary.unlink(missing_ok=True)

    def source(self, quote):
        if quote.kind == "draft" and quote.source_quote_id:
            with self.db.sessions() as session:
                original = require(session, quote.source_quote_id)
                return self.source(original)
        if not quote.source_storage_path:
            raise HTTPException(404, "연결된 원본이 없습니다.")
        path = (self.files / quote.source_storage_path).resolve()
        if path.parent != self.files.resolve() or not path.is_file():
            raise HTTPException(404, "원본 파일을 찾을 수 없습니다.")
        return path

    def start_extraction(self, request):
        provider = request.provider
        if provider == "auto":
            provider = self.config.extraction_provider
        if provider == "auto":
            key = self.config.upstage_api_key.get_secret_value()
            provider = "upstage" if key and not key.startswith("replace-") else "local"
        if provider not in ("local", "upstage"):
            raise HTTPException(422, "추출 provider 설정이 올바르지 않습니다.")
        if provider == "upstage" and not self.config.upstage_api_key.get_secret_value():
            raise HTTPException(503, "Upstage API 키가 필요합니다.")
        with self.db.sessions.begin() as session:
            q = require(session, request.quote_id)
            ensure_idle(q)
            if q.kind != "archive":
                raise HTTPException(409, "초안에는 문서 재추출을 실행할 수 없습니다.")
            has_data = bool(q.items) or any(v is not None and v != "" for k, v in q.payload.items() if k not in ("raw_fields", "review_note"))
            if (q.extraction_status == "completed" or has_data) and not request.force:
                raise HTTPException(409, "추출·검토 값이 있습니다. 덮어쓸 재추출은 force=true로 명시하세요.")
            self.source(q)
            q.status, q.extraction_status, q.updated_at = "extracting", "queued", now()
            job = Job(id=uid(), quote_id=q.id, kind="extract", provider=provider)
            session.add(job)
            record(session, q, "extraction_started")
            return self.job_data(job)

    @staticmethod
    def job_data(job):
        return {"job_id": job.id, "quote_id": job.quote_id, "kind": job.kind, "provider": job.provider, "status": job.status, "result": job.result or {}, "error": job.error, "created_at": job.created_at, "updated_at": job.updated_at}

    def run_extraction(self, job_id):
        try:
            with self.db.sessions.begin() as session:
                job = session.get(Job, job_id)
                if not job or job.status != "queued":
                    return
                job.status, job.updated_at = "running", now()
                q = require(session, job.quote_id)
                q.extraction_status = "running"
                content = self.source(q).read_bytes()
                suffix, provider = Path(q.source_filename).suffix.lower(), job.provider
            document = read_document(content, suffix, self.config.max_document_pages)
            remote = {}
            if provider == "upstage":
                pdf = content if suffix == ".pdf" else make_pdf("견적서 XLSX 셀·표 원문", document["text"].splitlines(), self.config.pdf_font_path)
                remote = self.agent.run(pdf, self.config.quote_extract_agent_id, self.config.quote_extract_config_id)
                extracted = remote["data"]
            else:
                extracted = local_extract(document)
            # Preserve explicitly written tax treatment even when the Studio schema
            # only returns tax_rate. No jurisdictional tax defaults are introduced.
            tax_fields = local_extract({"text": document["text"], "tables": []})
            for key in ("tax_terms", "tax_basis"):
                if not extracted.get(key) and tax_fields.get(key):
                    extracted[key] = tax_fields[key]
            fields, warnings = normalize_result(extracted)
            warnings += document["warnings"]
            if provider == "local":
                warnings.append("로컬 규칙 기반 추출입니다. 다양한 양식의 의미 분류는 Studio 추출 또는 담당자 확인이 필요합니다.")
            with self.db.sessions.begin() as session:
                job = session.get(Job, job_id)
                q = require(session, job.quote_id)
                set_fields(q, fields)
                q.extraction_raw = {"provider": provider, "text": document["text"], "fields": extracted, "warnings": warnings,
                                    **{k: v for k, v in remote.items() if k != "data"}}
                q.status, q.extraction_status = "review_required", "completed"
                record(session, q, "extraction_completed")
                job.status, job.result, job.updated_at = "completed", {"quote_id": q.id, "version": q.version, "warnings": warnings}, now()
        except Exception as exc:
            message = str(exc) if isinstance(exc, (DocumentError, AgentError)) else "추출 결과 처리에 실패했습니다. 원본 형식과 에이전트 설정을 확인하세요."
            self.fail_job(job_id, message)

    def fail_job(self, job_id, message):
        with self.db.sessions.begin() as session:
            job = session.get(Job, job_id)
            if not job:
                return
            job.status, job.error, job.updated_at = "failed", message, now()
            if job.kind == "extract":
                q = require(session, job.quote_id)
                q.status, q.extraction_status, q.updated_at = "review_required", "failed", now()
                record(session, q, "extraction_failed")

    def create_draft(self, quote_id, request: DraftRequest):
        with self.db.sessions.begin() as session:
            source = require(session, quote_id)
            ensure_idle(source)
            check_version(source, request.overrides.expected_version)
            fields = clean_fields(source)
            original_fields = copy.deepcopy(fields)
            changes = request.overrides.model_dump(mode="json", exclude_unset=True, exclude={"expected_version"})
            fields.update(changes)
            fields["items"] = fields.get("items") or []
            fields["raw_fields"] = fields.get("raw_fields") or {}
            if "quote_number" not in changes:
                fields["quote_number"] = None
            if "issue_date" not in changes:
                fields["issue_date"] = None
            for key in ("valid_until", "delivery_date"):
                if key not in changes:
                    fields[key] = None
            fields = calculate_draft(fields, request.tax_rate, request.tax_basis)
            draft = Quote(id=uid(), kind="draft", source_quote_id=source.id, extraction_status="not_applicable")
            set_fields(draft, fields)
            session.add(draft)
            draft.extraction_raw = {"source_snapshot": original_fields, "source_version": source.version, "changes": changes}
            record(session, draft, "draft_created")
            return detail(draft)

    def start_agent(self, request):
        if len(set(request.quote_ids)) != len(request.quote_ids):
            raise HTTPException(422, "견적 ID가 중복되었습니다.")
        if request.kind == "compare" and len(request.quote_ids) < 2:
            raise HTTPException(422, "비교에는 견적이 2개 이상 필요합니다.")
        if request.kind == "draft" and len(request.quote_ids) != 1:
            raise HTTPException(422, "초안에는 원본 견적 1개가 필요합니다.")
        if not self.config.upstage_api_key.get_secret_value():
            raise HTTPException(503, "Upstage API 키가 필요합니다.")
        with self.db.sessions.begin() as session:
            snapshots = []
            for identifier in request.quote_ids:
                q = require(session, identifier)
                ensure_idle(q)
                snapshots.append(detail(q))
            job = Job(id=uid(), quote_id=request.quote_ids[0], kind=request.kind, provider="upstage", result={"input": snapshots, "draft_request": request.draft_request.model_dump(mode="json") if request.draft_request else None})
            session.add(job)
            session.flush()
            return self.job_data(job)

    def run_agent(self, job_id):
        try:
            with self.db.sessions.begin() as session:
                job = session.get(Job, job_id)
                if not job or job.status != "queued":
                    return
                job.status, job.updated_at = "running", now()
                payload, kind = copy.deepcopy(job.result), job.kind
            pdf = agent_input(f"QuoteFlow {kind} 입력 - 저장된 견적과 사용자 지정 변경", payload, self.config.pdf_font_path)
            agent_id = getattr(self.config, f"quote_{kind}_agent_id")
            config_id = getattr(self.config, f"quote_{kind}_config_id")
            remote = self.agent.run(pdf, agent_id, config_id)
            result = remote["data"]
            if kind == "compare":
                if result.get("comparison_status") not in ("comparable", "conditional", "insufficient_data"):
                    raise AgentError("비교 에이전트의 상태 값이 올바르지 않습니다.")
                for key in ("comparison_rows_json", "comparable_pairs_json", "excluded_rows_json"):
                    result[key.removesuffix("_json")] = parse_json_field(result.get(key), [])
                    if not isinstance(result[key.removesuffix("_json")], list):
                        raise AgentError("비교 에이전트의 배열 형식이 올바르지 않습니다.")
                result["verified_comparison"] = compare_quotes(payload["input"])
            else:
                if result.get("draft_status") not in ("needs_input", "needs_review"):
                    raise AgentError("초안 에이전트의 상태 값이 올바르지 않습니다.")
                for key, default in (("draft_items_json", []), ("terms_json", {}), ("changes_json", [])):
                    parsed = parse_json_field(result.get(key), default)
                    if not isinstance(parsed, type(default)):
                        raise AgentError("초안 에이전트의 결과 형식이 올바르지 않습니다.")
                    result[key.removesuffix("_json")] = parsed
                result["notice"] = "AI 제안입니다. 사용자 확정 후 원본 복사 API로 초안을 생성하세요."
            with self.db.sessions.begin() as session:
                job = session.get(Job, job_id)
                job.status, job.result, job.updated_at = "completed", {**remote, "data": result}, now()
        except Exception as exc:
            self.fail_job(job_id, str(exc) if isinstance(exc, AgentError) else "에이전트 결과 처리에 실패했습니다.")
