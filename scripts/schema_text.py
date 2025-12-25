# schema_text.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import psycopg2


@dataclass(frozen=True)
class SchemaText:
    db_id: str
    text: str


def _quote_ident(ident: str) -> str:
    """
    Best-effort identifier quoting for display (not for SQL execution).
    Spider names can include spaces; we keep them as-is in the text.
    """
    return ident


def build_schema_text(
    conn: psycopg2.extensions.connection,
    db_id: str,
    *,
    use_original_names: bool = True,
    include_types: bool = False,
    max_columns_per_table: Optional[int] = None,
    max_total_chars: Optional[int] = None,
) -> SchemaText:
    """
    Generate a compact textual schema description for a given Spider db_id.

    Assumes the catalog tables exist:
      - spider_tables(db_id, table_id, name, name_original)
      - spider_columns(db_id, column_id, table_id, name, name_original, col_type)
      - spider_primary_keys(db_id, column_id)
      - spider_foreign_keys(db_id, from_column_id, to_column_id)

    Args:
        conn: psycopg2 connection
        db_id: Spider database identifier
        use_original_names: if True, use name_original fields (recommended for SQL generation)
        include_types: if True, append ": <type>" after each column
        max_columns_per_table: if set, truncate columns listing per table
        max_total_chars: if set, truncate final text to this many chars (soft truncation)

    Returns:
        SchemaText(db_id, text)
    """
    table_name_field = "name_original" if use_original_names else "name"
    col_name_field = "name_original" if use_original_names else "name"

    with conn.cursor() as cur:
        # Tables
        cur.execute(
            f"""
            SELECT table_id, {table_name_field}
            FROM spider_tables
            WHERE db_id = %s
            ORDER BY table_id
            """,
            (db_id,),
        )
        tables: List[Tuple[int, str]] = cur.fetchall()
        if not tables:
            raise ValueError(f"Unknown db_id or no tables found: {db_id}")

        table_id_to_name: Dict[int, str] = {tid: tname for tid, tname in tables}

        # Columns grouped by table_id
        cur.execute(
            f"""
            SELECT table_id, {col_name_field}, col_type
            FROM spider_columns
            WHERE db_id = %s AND table_id IS NOT NULL
            ORDER BY table_id, column_id
            """,
            (db_id,),
        )
        cols_by_table: Dict[int, List[Tuple[str, str]]] = {}
        for tid, cname, ctype in cur.fetchall():
            cols_by_table.setdefault(int(tid), []).append((str(cname), str(ctype)))

        # Primary keys -> column_id -> (table_id, colname)
        cur.execute(
            f"""
            SELECT c.table_id, c.{col_name_field}
            FROM spider_primary_keys pk
            JOIN spider_columns c
              ON c.db_id = pk.db_id AND c.column_id = pk.column_id
            WHERE pk.db_id = %s
              AND c.table_id IS NOT NULL
            ORDER BY c.table_id, c.column_id
            """,
            (db_id,),
        )
        pks_by_table: Dict[int, List[str]] = {}
        for tid, cname in cur.fetchall():
            pks_by_table.setdefault(int(tid), []).append(str(cname))

        # Foreign keys -> resolve to table/column names
        cur.execute(
            f"""
            SELECT
              c_from.table_id AS from_table_id,
              c_from.{col_name_field} AS from_col,
              c_to.table_id AS to_table_id,
              c_to.{col_name_field} AS to_col
            FROM spider_foreign_keys fk
            JOIN spider_columns c_from
              ON c_from.db_id = fk.db_id AND c_from.column_id = fk.from_column_id
            JOIN spider_columns c_to
              ON c_to.db_id = fk.db_id AND c_to.column_id = fk.to_column_id
            WHERE fk.db_id = %s
              AND c_from.table_id IS NOT NULL
              AND c_to.table_id IS NOT NULL
            ORDER BY c_from.table_id, c_from.column_id
            """,
            (db_id,),
        )
        fks: List[Tuple[int, str, int, str]] = [
            (int(a), str(b), int(c), str(d)) for a, b, c, d in cur.fetchall()
        ]

    lines: List[str] = []
    lines.append("You are given the following database schema.")
    lines.append("")
    lines.append(f"Database: {db_id}")
    lines.append("")
    lines.append("Tables:")

    for tid, tname in tables:
        cols = cols_by_table.get(tid, [])
        if max_columns_per_table is not None and len(cols) > max_columns_per_table:
            shown = cols[:max_columns_per_table]
            omitted = len(cols) - max_columns_per_table
        else:
            shown = cols
            omitted = 0

        if include_types:
            cols_txt = ", ".join(f"{_quote_ident(c)}:{t}" for c, t in shown)
        else:
            cols_txt = ", ".join(_quote_ident(c) for c, _ in shown)

        if omitted > 0:
            cols_txt = f"{cols_txt}, … (+{omitted} more)"

        lines.append(f"- {_quote_ident(tname)}({cols_txt})")

    # Foreign keys
    lines.append("")
    if fks:
        lines.append("Foreign keys:")
        for from_tid, from_col, to_tid, to_col in fks:
            from_table = table_id_to_name.get(from_tid, f"table_{from_tid}")
            to_table = table_id_to_name.get(to_tid, f"table_{to_tid}")
            lines.append(
                f"- {_quote_ident(from_table)}.{_quote_ident(from_col)} "
                f"references {_quote_ident(to_table)}.{_quote_ident(to_col)}"
            )
    else:
        lines.append("Foreign keys: (none)")

    # Primary keys
    lines.append("")
    any_pk = any(pks_by_table.values())
    if any_pk:
        lines.append("Primary keys:")
        for tid, _ in tables:
            pk_cols = pks_by_table.get(tid, [])
            if pk_cols:
                tname = table_id_to_name.get(tid, f"table_{tid}")
                lines.append(f"- {_quote_ident(tname)}: {', '.join(map(_quote_ident, pk_cols))}")
    else:
        lines.append("Primary keys: (none)")

    text = "\n".join(lines)

    if max_total_chars is not None and len(text) > max_total_chars:
        # Soft truncation: keep header + tables, then truncate rest
        text = text[: max_total_chars - 1] + "…"

    return SchemaText(db_id=db_id, text=text)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate textual schema for a Spider db_id.")
    parser.add_argument("--dsn", required=True, help="PostgreSQL DSN")
    parser.add_argument("--db-id", required=True, help="Spider db_id")
    parser.add_argument("--no-original", action="store_true", help="Use normalized names instead of original")
    parser.add_argument("--types", action="store_true", help="Include column types")
    parser.add_argument("--max-cols", type=int, default=None, help="Max columns per table")
    parser.add_argument("--max-chars", type=int, default=None, help="Max total output characters")

    args = parser.parse_args()

    conn = psycopg2.connect(dsn=args.dsn)
    try:
        schema = build_schema_text(
            conn,
            args.db_id,
            use_original_names=not args.no_original,
            include_types=args.types,
            max_columns_per_table=args.max_cols,
            max_total_chars=args.max_chars,
        )
        print(schema.text)
    finally:
        conn.close()
