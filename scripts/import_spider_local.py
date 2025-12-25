from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from infrastructure.persistence.tables import (
    DataContextTable,
    QuestionTable,
    question_data_contexts,
)

# -------------------------
# Config / Errors
# -------------------------

@dataclass(frozen=True)
class ImportError(RuntimeError):
    msg: str


def _find_file(root: Path, filename: str) -> Optional[Path]:
    hits = list(root.rglob(filename))
    if not hits:
        return None
    # prefer shortest path (closest to root)
    hits.sort(key=lambda p: len(p.parts))
    return hits[0]


def _find_database_dir(root: Path) -> Optional[Path]:
    # Spider layout typically has database/ folder
    hits = [p for p in root.rglob("database") if p.is_dir()]
    if not hits:
        return None
    hits.sort(key=lambda p: len(p.parts))
    return hits[0]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _iter_spider_examples(*paths: Optional[Path]) -> Iterable[Dict[str, Any]]:
    for p in paths:
        if p is None or not p.exists():
            continue
        data = _load_json(p)
        if not isinstance(data, list):
            raise ImportError(f"Expected list in {p}, got {type(data)}")
        for ex in data:
            yield ex


def _sqlite_path_for_db(database_dir: Path, db_id: str) -> Optional[Path]:
    # usually: database/<db_id>/<db_id>.sqlite
    candidate = database_dir / db_id / f"{db_id}.sqlite"
    if candidate.exists():
        return candidate
    # fallback: search
    hits = list((database_dir / db_id).glob("*.sqlite")) if (database_dir / db_id).exists() else []
    return hits[0] if hits else None


def _reset_tables(session: Session) -> None:
    session.execute(question_data_contexts.delete())
    session.query(QuestionTable).delete()
    session.query(DataContextTable).delete()
    session.commit()


# -------------------------
# Import logic
# -------------------------

def upsert_contexts(
    session: Session,
    tables_json: List[Dict[str, Any]],
    database_dir: Path,
    storage_prefix: str,
) -> Dict[str, UUID]:
    """
    Returns mapping db_id -> context_id.
    """
    db_to_context_id: Dict[str, UUID] = {}

    for entry in tables_json:
        db_id = entry.get("db_id")
        if not db_id:
            continue

        sqlite_path = _sqlite_path_for_db(database_dir, db_id)
        storage_link: Optional[str] = None
        if sqlite_path is not None:
            # store a "stable" reference usable by your workers
            # Example: datasets/spider/database/<db_id>/<db_id>.sqlite
            rel = sqlite_path.as_posix()
            storage_link = rel

        # name: db_id (simple)
        # schema_definition: Spider table entry is JSON-serializable already
        existing = session.execute(
            select(DataContextTable).where(DataContextTable.name == db_id)
        ).scalar_one_or_none()

        if existing is None:
            ctx_id = uuid4()
            session.add(
                DataContextTable(
                    id=ctx_id,
                    name=db_id,
                    schema_definition=entry,  # JSONB
                    storage_link=storage_link or f"{storage_prefix}/{db_id}.sqlite",
                    is_active=True,
                )
            )
            db_to_context_id[db_id] = ctx_id
        else:
            # update minimal fields
            existing.schema_definition = entry
            if storage_link:
                existing.storage_link = storage_link
            existing.is_active = True
            db_to_context_id[db_id] = existing.id

    session.commit()
    return db_to_context_id


def import_questions(
    session: Session,
    examples: Iterable[Dict[str, Any]],
    db_to_context_id: Dict[str, UUID],
    *,
    category: Optional[str],
    batch_size: int = 1000,
) -> Tuple[int, int]:
    """
    Inserts questions and link table.
    Returns (inserted_questions, inserted_links)
    """
    inserted_q = 0
    inserted_links = 0

    buffer_questions: List[QuestionTable] = []
    buffer_links: List[Dict[str, Any]] = []

    def flush() -> None:
        nonlocal inserted_q, inserted_links, buffer_questions, buffer_links
        if buffer_questions:
            session.add_all(buffer_questions)
            inserted_q += len(buffer_questions)
            buffer_questions = []
        if buffer_links:
            session.execute(question_data_contexts.insert(), buffer_links)
            inserted_links += len(buffer_links)
            buffer_links = []
        session.commit()

    for ex in examples:
        db_id = ex.get("db_id")
        if not db_id:
            continue

        ctx_id = db_to_context_id.get(db_id)
        if ctx_id is None:
            # context missing => skip
            continue

        question_text = ex.get("question")
        sql_gold = ex.get("query")

        if not question_text or not sql_gold:
            continue

        q_id = uuid4()
        buffer_questions.append(
            QuestionTable(
                id=q_id,
                content=question_text,
                gold_code=sql_gold,
                language="SQL",
                category=category or db_id,  # useful for filtering; keep db_id by default
                difficulty=None,
            )
        )
        buffer_links.append({"question_id": q_id, "context_id": ctx_id})

        if len(buffer_questions) >= batch_size:
            flush()

    flush()
    return inserted_q, inserted_links


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Spider datasets from local pretreated folder into Postgres.")
    parser.add_argument("--root", default="datasets/pretraited", help="Root folder where Spider data is located.")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL", ""), help="SQLAlchemy DB URL (or env DATABASE_URL).")
    parser.add_argument("--reset", action="store_true", help="Delete existing contexts/questions/links before import.")
    parser.add_argument("--include-train", action="store_true", help="Import training splits too (train_spider + train_others).")
    parser.add_argument("--include-dev", action="store_true", help="Import dev split too (dev.json).")
    parser.add_argument("--category", default=None, help="Force category for imported questions (default: db_id).")
    parser.add_argument("--batch-size", type=int, default=1000, help="Insert batch size.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise ImportError(f"Root does not exist: {root}")

    if not args.db_url:
        raise ImportError("Missing --db-url and env DATABASE_URL is not set.")

    tables_path = _find_file(root, "tables.json")
    if tables_path is None:
        raise ImportError(f"Could not find tables.json under {root}")

    train_spider = _find_file(root, "train_spider.json")
    train_others = _find_file(root, "train_others.json")
    dev_path = _find_file(root, "dev.json")

    database_dir = _find_database_dir(root)
    if database_dir is None:
        raise ImportError(f"Could not find database/ directory under {root}")

    tables_json = _load_json(tables_path)
    if not isinstance(tables_json, list):
        raise ImportError(f"tables.json must be a list, got {type(tables_json)}")

    engine = create_engine(args.db_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with SessionLocal() as session:
        if args.reset:
            print("🧨 Resetting existing DataContexts / Questions / links…")
            _reset_tables(session)

        print(f"📦 Importing contexts from: {tables_path}")
        db_to_ctx = upsert_contexts(
            session=session,
            tables_json=tables_json,
            database_dir=database_dir,
            storage_prefix=str(database_dir),
        )
        print(f"✅ Contexts upserted: {len(db_to_ctx)}")

        total_q = 0
        total_links = 0

        if args.include_train:
            print("📥 Importing TRAIN questions…")
            q, l = import_questions(
                session=session,
                examples=_iter_spider_examples(train_spider, train_others),
                db_to_context_id=db_to_ctx,
                category=args.category,
                batch_size=args.batch_size,
            )
            total_q += q
            total_links += l

        if args.include_dev:
            print("📥 Importing DEV questions…")
            q, l = import_questions(
                session=session,
                examples=_iter_spider_examples(dev_path),
                db_to_context_id=db_to_ctx,
                category=args.category,
                batch_size=args.batch_size,
            )
            total_q += q
            total_links += l

        print(f"✅ Imported questions: {total_q}")
        print(f"✅ Created links:     {total_links}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
