from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import Settings


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(20), default="archive")
    source_quote_id: Mapped[str | None] = mapped_column(String(36))
    source_filename: Mapped[str | None] = mapped_column(Text)
    source_storage_path: Mapped[str | None] = mapped_column(Text)
    source_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="review_required", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    extraction_raw: Mapped[dict] = mapped_column(JSON, default=dict)
    extraction_status: Mapped[str] = mapped_column(String(30), default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)
    deleted_at: Mapped[str | None] = mapped_column(String(40), index=True)
    items: Mapped[list["Item"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="Item.line_number")
    __mapper_args__ = {"version_id_col": version}


class Item(Base):
    __tablename__ = "quote_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"), index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    item_name: Mapped[str] = mapped_column(Text)
    item_name_original: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)


class Revision(Base):
    __tablename__ = "quote_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(40))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Job(Base):
    __tablename__ = "agent_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    quote_id: Mapped[str | None] = mapped_column(ForeignKey("quotes.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    provider: Mapped[str] = mapped_column(String(30))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class Database:
    def __init__(self, config: Settings):
        config.data_dir.mkdir(parents=True, exist_ok=True)
        url = config.database_url.get_secret_value() or f"sqlite:///{(config.data_dir / 'quotes.db').as_posix()}"
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=args, pool_pre_ping=True)
        if self.engine.dialect.name == "sqlite":
            @event.listens_for(self.engine, "connect")
            def sqlite_setup(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA journal_mode=WAL")
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.create_schema = self.engine.dialect.name == "sqlite" or config.auto_create_schema

    def initialize(self):
        if self.create_schema:
            Base.metadata.create_all(self.engine)
        from sqlalchemy import select
        with self.sessions.begin() as session:
            for job in session.scalars(select(Job).where(Job.status.in_(["queued", "running"]))):
                job.status, job.error, job.updated_at = "failed", "서버가 재시작되어 작업이 중단되었습니다. 다시 실행하세요.", now()
                if job.kind == "extract" and job.quote_id:
                    quote = session.get(Quote, job.quote_id)
                    if quote:
                        quote.extraction_status, quote.status = "failed", "review_required"
