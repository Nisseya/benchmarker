import json
import psycopg2
from psycopg2.extras import execute_values, Json

def ingest_tables_json(conn, path: str):
    data = json.load(open(path, "r", encoding="utf-8"))

    with conn:
        with conn.cursor() as cur:
            for s in data:
                db_id = s["db_id"]

                # 1) database row
                cur.execute(
                    """
                    INSERT INTO spider_databases (db_id, table_names, table_names_original, raw)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (db_id) DO UPDATE SET
                      table_names = EXCLUDED.table_names,
                      table_names_original = EXCLUDED.table_names_original,
                      raw = EXCLUDED.raw
                    """,
                    (db_id, Json(s["table_names"]), Json(s["table_names_original"]), Json(s)),
                )

                # 2) tables
                tables_rows = [
                    (db_id, i, s["table_names"][i], s["table_names_original"][i])
                    for i in range(len(s["table_names"]))
                ]
                execute_values(
                    cur,
                    """
                    INSERT INTO spider_tables (db_id, table_id, name, name_original)
                    VALUES %s
                    ON CONFLICT (db_id, table_id) DO UPDATE SET
                      name = EXCLUDED.name,
                      name_original = EXCLUDED.name_original
                    """,
                    tables_rows,
                )

                # 3) columns (flatten, aligned by index)
                cols_rows = []
                for col_id, ((t_id, name), (_, name_orig), col_type) in enumerate(
                    zip(s["column_names"], s["column_names_original"], s["column_types"])
                ):
                    table_id = None if t_id == -1 else int(t_id)
                    cols_rows.append((db_id, col_id, table_id, name, name_orig, col_type))

                execute_values(
                    cur,
                    """
                    INSERT INTO spider_columns (db_id, column_id, table_id, name, name_original, col_type)
                    VALUES %s
                    ON CONFLICT (db_id, column_id) DO UPDATE SET
                      table_id = EXCLUDED.table_id,
                      name = EXCLUDED.name,
                      name_original = EXCLUDED.name_original,
                      col_type = EXCLUDED.col_type
                    """,
                    cols_rows,
                )

                # 4) primary keys
                pk_rows = [(db_id, int(cid)) for cid in s.get("primary_keys", [])]
                if pk_rows:
                    execute_values(
                        cur,
                        """
                        INSERT INTO spider_primary_keys (db_id, column_id)
                        VALUES %s
                        ON CONFLICT DO NOTHING
                        """,
                        pk_rows,
                    )

                # 5) foreign keys
                fk_rows = [(db_id, int(a), int(b)) for a, b in s.get("foreign_keys", [])]
                if fk_rows:
                    execute_values(
                        cur,
                        """
                        INSERT INTO spider_foreign_keys (db_id, from_column_id, to_column_id)
                        VALUES %s
                        ON CONFLICT DO NOTHING
                        """,
                        fk_rows,
                    )

if __name__ == "__main__":
    conn = psycopg2.connect(
        dsn="postgresql://nisseya:password123@localhost:5432/benchmark_db"
    )

    ingest_tables_json(conn, "datasets/tables.json")
    ingest_tables_json(conn, "datasets/test_tables.json")
    conn.close()
