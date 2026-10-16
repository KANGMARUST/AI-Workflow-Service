"""Generate initial PostgreSQL DDL without connecting to any database."""
import sys
from pathlib import Path

from sqlalchemy import create_mock_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import Base


def main():
    statements = []
    def dump(sql, *args, **kwargs):
        compiled = str(sql.compile(dialect=engine.dialect)).strip()
        statements.append("\n".join(line.rstrip() for line in compiled.splitlines())+";")
    engine = create_mock_engine("postgresql+psycopg://", dump)
    Base.metadata.create_all(engine)
    path = Path(__file__).resolve().parents[1] / "supabase" / "schema.sql"
    header = "-- QuoteFlow initial schema. Review before applying to an EMPTY database.\n-- Replaces the earlier unimplemented draft; this is NOT an upgrade migration.\n-- App uses a server-side PostgreSQL role. Do not expose these tables through an anonymous REST role.\n-- Decimal source values are canonical JSON strings to retain precision across SQLite/PostgreSQL.\n\n"
    protections = "\n".join(f"ALTER TABLE {table.name} ENABLE ROW LEVEL SECURITY;" for table in Base.metadata.sorted_tables)
    path.write_text(header+"\n\n".join(statements)+"\n\n-- No anonymous policies. The server connects with its trusted DB role.\n"+protections+"\n", encoding="utf-8")
    print("Generated PostgreSQL initial schema (no database contacted).")


if __name__ == "__main__":
    main()
